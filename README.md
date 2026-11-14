# acl

> The Animation Compression Library (skeletal clips and scalar tracks compressed within a stated error, played back at any time) and the Realtime Math library it is built on, through C++23 modules.

**English** · [简体中文](README.zh.md) · [Upstream ACL](https://github.com/nfrechette/acl) · [Upstream RTM](https://github.com/nfrechette/rtm) · [Releases](https://github.com/mcpplibs/acl-m/releases) · [mcpp](https://github.com/mcpp-community/mcpp) · [Index](https://github.com/mcpplibs/mcpp-index)

[![C++23](https://img.shields.io/badge/C%2B%2B-23-blue.svg)](https://en.cppreference.com/w/cpp/23)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![mcpp-community](https://img.shields.io/badge/mcpp--community-mwrap-blue)](https://github.com/mcpp-community)
[![CI](https://github.com/mcpplibs/acl-m/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mcpplibs/acl-m/actions/workflows/ci.yml)

The upstream C++ API is unchanged: `acl::track_array_qvvf`, `acl::compress_track_list`,
`acl::decompression_context`, `acl::track_writer`, `rtm::quatf`, `rtm::qvvf` and every
other public name are the upstream entities, in the namespaces upstream declares them
in. ACL 2.1.0 and the RTM 2.2.0 it pins are vendored from their releases (one upstream
fix applied, `patches/`) and configured with `RTM_NO_INTRINSICS` and
`ACL_NO_INTRINSICS`, with no contraction of `a*b+c` into an FMA and no fast math
(`-ffp-contract=off`, `-fno-fast-math`), the same in every profile: the same clip
gives the same compressed bytes, and the same compressed clip the same poses at the
same times, on every platform (pinned hashes in the tests, compared on every CI row).

## Modules

- `import mcpplibs.mwrap.acl;`: every public name of ACL's and RTM's headers — 197 types and 454 functions (templates and overloads under one name each) in `acl`, `rtm` and `rtm::constants`

> More Modules API -> [ACL's README](upstream/acl/README.md), [RTM's README](upstream/rtm/README.md)

## Getting started

```sh
mcpp new clip --template mcpplibs.mwrap.acl@2.1.0
cd clip
mcpp run
```

The default template compresses an arm of three joints waving for two seconds
within 0.1 mm and plays it back at five times, between the samples too.

```toml
[dependencies]
mcpplibs.mwrap.acl = "2.1.0"

# For the same poses everywhere: RTM's inline math is compiled in your units too.
[build]
cxxflags = ["-ffp-contract=off"]
```

```cpp
import std;
import mcpplibs.mwrap.acl;

int main() {
    acl::ansi_allocator allocator;
    acl::track_array_qvvf clip(allocator, 3);   // track_qvvf::make_reserve per joint, samples as rtm::qvv_set
    acl::compression_settings settings = acl::get_default_compression_settings();
    acl::compressed_tracks* compressed = nullptr; // compress_track_list(allocator, clip, settings, compressed, stats)
    acl::decompression_context<acl::default_transform_decompression_settings> context;
    // context.initialize(*compressed); context.seek(time, …); context.decompress_tracks(writer);
}
```

## Constants

Fifteen `constexpr` objects at namespace scope have internal linkage (each
includer has its own) and a module cannot export them. They are in
`mcpplibs::mwrap::acl` under their names, with their types and values —
`k_invalid_track_index`, `k_num_quality_tiers`, `k_highest_bit_rate`,
`k_lowest_bit_rate`, `k_invalid_bit_rate`, `k_num_database_tiers`,
`k_bit_rate_num_bits` (an array) … ACL and RTM have no macros a program spells:
there is no `.macros` module.

## What is and is not wrapped

- Wrapped: every name of the headers under `acl/` (compression, decompression, core, math) and `rtm/` (666 in all). `tools/surface.py` derives the list from the headers as clang reads them; the implementation namespaces (`*_impl`) are left out.
- Not here: ACL's `io` (reading and writing clips as SJSON, which needs the sjson-cpp library; its forward declarations come with `acl/fwd.h` and are vendored for that), the tools, the Unreal and other engine plugins, and the tests.
- Scalar math: `RTM_NO_INTRINSICS` and `ACL_NO_INTRINSICS` keep SSE, AVX and NEON out, because RTM's NEON paths fuse multiply and add and its SSE paths use approximate reciprocals — the bits would differ by platform. On x86-64 a 64-joint pose decompresses in 26.8 ns per joint against 17.2 with SSE (GCC 16, `-O2`, same machine), and the compressed bytes are not the SIMD build's.
- Not a `compat` package: the index has no traditional ACL or RTM package.
- The compression error is ACL's own measure (the distance of points at `shell_distance` from each joint, in object space); ACL nearly guarantees `precision`, and the tests measure it.

## Verification

- `mcpp test`: a five-joint chain compressed twice to the same bytes, the error measured against the raw clip, poses at five times; the compressed bytes and the poses pinned; the adapted constants.
- `python3 tools/check_exports.py`: the module is exactly `tools/surface.json`; given a clang++ (required on CI's LLVM row) the record is derived again from the headers and compared.
- `python3 tools/test_template.py`: `mcpp new` from an installed copy, a strict build, and a run of the generated project.
- CI: Linux x86-64 and arm64 (GCC 16, LLVM 23), macOS and Windows (LLVM 23), each in the dev and release profiles, and wasm32 under node — the same pinned hashes on every row.

## License

The wrapper is Apache-2.0 (mcpp-community). ACL is MIT, © 2017 Nicholas
Frechette & Animation Compression Library contributors; RTM is MIT, © 2018
Nicholas Frechette. Upstream's READMEs and licenses are kept in
`upstream/acl/` and `upstream/rtm/` and deployed with a program's licenses. Provenance: `upstream/documents.json`.
