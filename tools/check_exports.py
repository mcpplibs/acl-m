#!/usr/bin/env python3
"""Audit the module surface against the public headers.

src/acl.cppm must be exactly what tools/surface.py writes from
tools/surface.json, and every name of that record must be found in a header
under upstream/acl/includes or upstream/rtm/includes. With a clang++ (--clang, or MWRAP_CLANG) the record
itself is derived again from the headers as the compiler reads them and must
be the same: no public name is left out, none is exported that is not there.
MWRAP_REQUIRE_CLANG=1 makes the second half mandatory (CI's LLVM row).
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import surface  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', default=os.environ.get('MWRAP_CLANG'))
    args = parser.parse_args()
    record = surface.record()
    written = surface.MODULE.read_text(encoding='utf-8')
    assert written == surface.module_text(record), 'src/acl.cppm is not what tools/surface.py --write gives'
    headers = ''.join(path.read_text(encoding='utf-8') for include in surface.INCLUDES for path in sorted(include.rglob('*.h')))
    count = exported = 0
    for namespace, kinds in record.items():
        for kind, names in kinds.items():
            for name in names:
                count += 1
                spelled = name
                # An operator is spelled with or without a space before its symbol.
                pattern = r'\boperator\s*' + re.escape(name.removeprefix('operator').strip()) if name.startswith('operator') and not name[8:9].isalnum() and name[8:9] != '_' \
                    else r'(?<![\w])' + re.escape(spelled) + r'(?![\w])'
                assert re.search(pattern, headers), f'{namespace}::{name} is in no header'
                if kind == 'internal':
                    continue
                if kind.startswith('adapted'):
                    assert re.search(rf'inline constexpr auto {re.escape(name)} = (std::to_array\()?::{re.escape(namespace)}::{re.escape(name)}', written), name
                else:
                    exported += 1
                    assert f'using ::{namespace}::{name};' in written, name
    if args.clang:
        derived = surface.derive(args.clang)
        assert derived == record, {namespace: sorted(set(sum(derived.get(namespace, {}).values(), [])) ^ set(sum(record.get(namespace, {}).values(), [])))
                                   for namespace in set(derived) | set(record)}
    else:
        assert os.environ.get('MWRAP_REQUIRE_CLANG') != '1', 'MWRAP_REQUIRE_CLANG=1 and no clang++ given'
    internal = sum(len(kinds.get('internal', [])) for kinds in record.values())
    print(f'{count} names: {exported} exported, {count - exported - internal} constants of internal linkage adapted, {internal} functions of internal '
          'linkage not exported; ' + ('the record is what clang derives from the headers' if args.clang else 'the record not derived again (no clang++ given)'))


if __name__ == '__main__':
    main()
