#!/usr/bin/env python3
"""The module's export list, derived from ACL's and RTM's headers.

With --clang <clang++> the headers are read by the compiler, configured as
this package builds them (mcpp.toml): every name declared at namespace scope
in `acl` and `rtm` and their nested namespaces by a header under
upstream/acl/includes/acl or upstream/rtm/includes/rtm is recorded in
tools/surface.json, by namespace and kind. src/acl.cppm is written from that
record (--write), one `using` a name: a using-declaration carries every
overload and every template of the name.

The libraries' implementation namespaces (every one whose name ends in
`_impl`: `acl::acl_impl`, `rtm::rtm_impl` …) are not exported: the public templates reach what
they use there without it.

An object at namespace scope declared `static`, or `constexpr` without
`inline`, has internal linkage: each translation unit that includes the
header has its own, and a module cannot export it. Such constants are
recorded as `adapted` and declared again, with their names, types and values,
in `mcpplibs::mwrap::acl` (and its nested namespaces of the same names: `rtm`
for RTM's). Functions of internal linkage are recorded as `internal` and not
exported.

The enumerators of an unscoped enumeration are names of the enclosing
namespace: they are recorded (`enumerators`) and exported with it.

Not read: acl/io (reading and writing clips as SJSON needs the sjson-cpp
library, which is not vendored; its forward declarations come in through
acl/fwd.h).
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
INCLUDES = (ROOT / 'upstream/acl/includes', ROOT / 'upstream/rtm/includes')
RECORD = ROOT / 'tools/surface.json'
MODULE = ROOT / 'src/acl.cppm'
# As the package builds the libraries (mcpp.toml's cxxflags): no SIMD intrinsics, the same arithmetic everywhere.
DEFINES = ('RTM_NO_INTRINSICS', 'ACL_NO_INTRINSICS')
# Upstream writes `template f(` without an argument list (decompress.impl.h), which clang 19 and later make an error.
FLAGS = ('-Wno-missing-template-arg-list-after-template-kw', '-Wno-deprecated-declarations')
# Headers that are not part of the C++ surface (see the docstring), and the implementation headers the public
# ones include.
EXCLUDED = ('acl/io/',)
IMPL = ('/impl/',)
FIRST = ()
ROOT_NAMESPACES = ('acl', 'rtm')

CONDITIONAL = {}
MEMBERS = {'CXXMethodDecl', 'CXXConstructorDecl', 'CXXDestructorDecl', 'CXXConversionDecl'}
KINDS = {
    'CXXRecordDecl': 'types', 'ClassTemplateDecl': 'types', 'EnumDecl': 'types', 'TypeAliasDecl': 'types', 'TypedefDecl': 'types',
    'TypeAliasTemplateDecl': 'types', 'FunctionDecl': 'functions', 'FunctionTemplateDecl': 'functions', 'VarDecl': 'constants',
    'VarTemplateDecl': 'constants',
}
# Declarations that name nothing of their own.
PASSED = {'UsingDirectiveDecl', 'UsingDecl', 'UsingShadowDecl', 'ClassTemplateSpecializationDecl', 'ClassTemplatePartialSpecializationDecl',
          'CXXDeductionGuideDecl', 'StaticAssertDecl', 'EmptyDecl', 'CXXMethodDecl', 'CXXConstructorDecl', 'CXXDestructorDecl',
          'CXXConversionDecl', 'FriendDecl', 'LinkageSpecDecl', 'FullComment', 'VarTemplateSpecializationDecl'}


def headers():
    """Every header the surface is read from, in the order they are included."""
    found = sorted(path.relative_to(include).as_posix() for include, root in zip(INCLUDES, ROOT_NAMESPACES) for path in (include / root).rglob('*.h'))
    return [header for header in found if not header.startswith(EXCLUDED) and not any(part in header for part in IMPL)]


def trees(clang):
    """Every top-level `namespace acl` and `namespace rtm` block of the translation unit that includes the headers."""
    with tempfile.TemporaryDirectory(prefix='acl-surface-') as directory:
        source = Path(directory) / 'all.cpp'
        source.write_text(''.join(f'#include <{header}>\n' for header in headers()), encoding='utf-8')
        # Function bodies are skipped: a body declares nothing at namespace scope, and the dump is a third the size.
        command = [clang, '-std=c++23', '-fsyntax-only', *[f'-I{include}' for include in INCLUDES], *[f'-D{define}' for define in DEFINES], *FLAGS,
                   '-Xclang', '-skip-function-bodies', '-Xclang', '-ast-dump=json',  str(source)]
        text = subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True).stdout
    return [tree for tree in json.loads(text).get('inner', []) if tree.get('kind') == 'NamespaceDecl' and tree.get('name') in ROOT_NAMESPACES]


def internal(node):
    return node.get('storageClass') == 'static' or (node.get('kind') == 'VarDecl' and not node.get('inline') and node.get('constexpr'))


def derive(clang):
    found = {}
    unknown = set()

    def walk(node, scope):
        kinds = found.setdefault(scope, {'types': set(), 'enumerators': set(), 'functions': set(), 'constants': set(), 'adapted': set(), 'adapted arrays': set(), 'internal': set()})
        for child in node.get('inner', []):
            kind, name = child.get('kind'), child.get('name')
            if kind == 'NamespaceDecl':
                assert name, f'an anonymous namespace in {scope}'
                if name.endswith('_impl'):
                    continue
                # An inline namespace's names are its parent's.
                walk(child, scope if child.get('isInline') else f'{scope}::{name}')
                continue
            if child.get('isImplicit') or not name:
                continue
            # Declared here, a member of something else (a nested class or a member template defined outside its
            # class, as the .inl files do): clang says so by the semantic parent it names.
            if 'parentDeclContextId' in child or (kind == 'FunctionTemplateDecl' and any(item.get('kind') in MEMBERS for item in child.get('inner', []))):
                continue
            if kind == 'VarDecl' and internal(child):
                assert child.get('constexpr'), f'a static object that is not constexpr: {scope}::{name}'
                kinds['adapted arrays' if child.get('type', {}).get('qualType', '').endswith(']') else 'adapted'].add(name)
            elif kind == 'FunctionDecl' and internal(child):
                kinds['internal'].add(name)
            elif kind in KINDS:
                kinds[KINDS[kind]].add(name)
                if kind == 'EnumDecl' and not child.get('scopedEnumTag'):
                    kinds['enumerators'] |= {item['name'] for item in child.get('inner', []) if item.get('kind') == 'EnumConstantDecl'}
            elif kind not in PASSED:
                unknown.add(f'{kind} {scope}::{name}')

    for tree in trees(clang):
        walk(tree, tree['name'])
    assert not unknown, sorted(unknown)
    return {namespace: {kind: sorted(names) for kind, names in kinds.items() if names} for namespace, kinds in sorted(found.items())}


def record():
    return json.loads(RECORD.read_text(encoding='utf-8'))


def module_text(surface=None):
    surface = surface or record()
    lines = ['// mcpplibs.mwrap.acl — the Animation Compression Library and the Realtime Math library it is built on, as a',
             '// C++ module. Every exported name is the upstream entity of the headers under <acl/…> and <rtm/…>, in the',
             '// namespace upstream declares it in: `acl`, `rtm` and their nested namespaces (not the implementation',
             '// ones). The libraries are configured as this package builds them (RTM_NO_INTRINSICS, ACL_NO_INTRINSICS).',
             '// Written by tools/surface.py from the headers as the compiler reads them (tools/surface.json;',
             '// tools/check_exports.py holds the three together).',
             'module;',
             *[f'#include <{header}>' for header in headers()],
             '',
             'export module mcpplibs.mwrap.acl;',
             '',
             'import std;',
             '']
    for namespace, kinds in surface.items():
        exported = [kind for kind in ('types', 'enumerators', 'constants', 'functions') if kinds.get(kind)]
        if not exported:
            continue
        lines.append(f'export namespace {namespace} {{')
        for kind, title in (('types', 'types'), ('enumerators', 'enumerators of unscoped enumerations'), ('constants', 'objects'),
                            ('functions', 'functions and operators')):
            names = kinds.get(kind, [])
            if names:
                lines.append(f'// {title}')
                for name in names:
                    condition = CONDITIONAL.get(f'{namespace}::{name}')
                    lines += [f'#if {condition}', f'using ::{namespace}::{name};', '#endif'] if condition else [f'using ::{namespace}::{name};']
        lines += [f'}}  // namespace {namespace}', '']
    lines += ["// The headers' constants of internal linkage (static, or constexpr and not inline: every includer has its",
              '// own, and none can be exported), again under their names with their types and values; an array as a',
              '// std::array of its elements.']
    for namespace, kinds in surface.items():
        names, arrays = kinds.get('adapted', []), kinds.get('adapted arrays', [])
        if not names and not arrays:
            continue
        target = 'mcpplibs::mwrap::acl' + ('' if namespace == 'acl' else '::' + namespace.removeprefix('acl::'))
        lines.append(f'export namespace {target} {{')
        lines += [f'inline constexpr auto {name} = ::{namespace}::{name};' for name in names]
        lines += [f'inline constexpr auto {name} = std::to_array(::{namespace}::{name});' for name in arrays]
        lines += [f'}}  // namespace {target}', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', help='derive tools/surface.json with this clang++')
    parser.add_argument('--write', action='store_true', help='write src/acl.cppm')
    args = parser.parse_args()
    if args.clang:
        RECORD.write_text(json.dumps(derive(args.clang), indent=1) + '\n', encoding='utf-8')
    if args.write:
        MODULE.write_text(module_text(), encoding='utf-8')
    for namespace, kinds in record().items():
        print(namespace + ': ' + ', '.join(f'{len(names)} {kind}' for kind, names in kinds.items()))


if __name__ == '__main__':
    sys.exit(main())
