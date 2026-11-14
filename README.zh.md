# acl

> Animation Compression Library（在给定误差内压缩骨骼动画片段与标量轨道，并在任意时刻回放）及其所依赖的 Realtime Math 库的 C++23 模块封装。

[English](README.md) · **简体中文** · [Upstream ACL](https://github.com/nfrechette/acl) · [Upstream RTM](https://github.com/nfrechette/rtm) · [Releases](https://github.com/mcpplibs/acl-m/releases) · [mcpp](https://github.com/mcpp-community/mcpp) · [Index](https://github.com/mcpplibs/mcpp-index)

[![C++23](https://img.shields.io/badge/C%2B%2B-23-blue.svg)](https://en.cppreference.com/w/cpp/23)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![mcpp-community](https://img.shields.io/badge/mcpp--community-mwrap-blue)](https://github.com/mcpp-community)
[![CI](https://github.com/mcpplibs/acl-m/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mcpplibs/acl-m/actions/workflows/ci.yml)

上游的 C++ API 保持原样：`acl::track_array_qvvf`、`acl::compress_track_list`、`acl::decompression_context`、
`acl::track_writer`、`rtm::quatf`、`rtm::qvvf` 以及其他公开名字都是上游的实体，在上游声明它们的命名空间里。
ACL 2.1.0 与它固定的 RTM 2.2.0 取自各自的发布包（应用了一个上游修复，见 `patches/`），以 `RTM_NO_INTRINSICS`、
`ACL_NO_INTRINSICS` 配置，构建时不把 `a*b+c` 合并为 FMA、不用快速数学（`-ffp-contract=off`、`-fno-fast-math`），
且每种配置都相同：同一个片段在每个平台上压缩出同样的字节，同一个压缩片段在同样的时刻给出同样的姿态
（测试里固定了哈希，在每一行 CI 上比对）。

## 模块

- `import mcpplibs.mwrap.acl;`：ACL 与 RTM 头文件里的全部公开名字——`acl`、`rtm`、`rtm::constants` 中共 197 个类型、454 个函数（模板与重载各算一个名字）

> 更多模块 API -> [ACL 的 README](upstream/acl/README.md)、[RTM 的 README](upstream/rtm/README.md)

## 快速开始

```sh
mcpp new clip --template mcpplibs.mwrap.acl@2.1.0
cd clip
mcpp run
```

默认模板把一条三个关节、挥动两秒的手臂压缩在 0.1 mm 以内，并在五个时刻（包括采样之间）回放。

```toml
[dependencies]
mcpplibs.mwrap.acl = "2.1.0"

# 要在各处得到同样的姿态：RTM 的内联数学也在你的编译单元里编译。
[build]
cxxflags = ["-ffp-contract=off"]
```

```cpp
import std;
import mcpplibs.mwrap.acl;

int main() {
    acl::ansi_allocator allocator;
    acl::track_array_qvvf clip(allocator, 3);   // 每个关节 track_qvvf::make_reserve，采样用 rtm::qvv_set
    acl::compression_settings settings = acl::get_default_compression_settings();
    acl::compressed_tracks* compressed = nullptr; // compress_track_list(allocator, clip, settings, compressed, stats)
    acl::decompression_context<acl::default_transform_decompression_settings> context;
    // context.initialize(*compressed); context.seek(time, …); context.decompress_tracks(writer);
}
```

## 常量

命名空间作用域里有 15 个 `constexpr` 对象是内部链接（每个包含者各有一份），模块无法导出。它们以原名、
原类型和原值放在 `mcpplibs::mwrap::acl` 中——`k_invalid_track_index`、`k_num_quality_tiers`、`k_highest_bit_rate`、
`k_lowest_bit_rate`、`k_invalid_bit_rate`、`k_num_database_tiers`、`k_bit_rate_num_bits`（数组）……ACL 与 RTM
没有需要程序书写的宏：不提供 `.macros` 模块。

## 封装了什么、没封装什么

- 已封装：`acl/`（compression、decompression、core、math）与 `rtm/` 下头文件的全部名字（共 666 个）。`tools/surface.py` 按 clang 读到的头文件推导出这份清单；实现用的命名空间（`*_impl`）不导出。
- 不在这里：ACL 的 `io`（以 SJSON 读写片段，需要 sjson-cpp 库；`acl/fwd.h` 会带上它的前向声明，因此随包携带）、工具、Unreal 等引擎插件和测试。
- 标量数学：`RTM_NO_INTRINSICS` 与 `ACL_NO_INTRINSICS` 关掉 SSE、AVX、NEON，因为 RTM 的 NEON 路径会合并乘加、SSE 路径用近似倒数——不同平台的位会不同。在 x86-64 上，一个 64 关节的姿态每关节解压 26.8 ns，SSE 构建为 17.2 ns（GCC 16、`-O2`、同一台机器）；压缩出的字节也与 SIMD 构建不同。
- 不是 `compat` 包：索引里没有传统的 ACL 或 RTM 包。
- 压缩误差是 ACL 自己的度量（离每个关节 `shell_distance` 处的点在物体空间里的距离）；ACL 基本保证 `precision`，测试会实测它。

## 验证

- `mcpp test`：五个关节的链压缩两次得到同样的字节，相对原始片段测量误差，在五个时刻取姿态；固定压缩字节与姿态的哈希；被改写的常量。
- `python3 tools/check_exports.py`：模块恰好是 `tools/surface.json`；给出 clang++ 时（CI 的 LLVM 行必须）从头文件重新推导并比对。
- `python3 tools/test_template.py`：从已安装的副本 `mcpp new`，严格构建，并运行生成的项目。
- CI：Linux x86-64 与 arm64（GCC 16、LLVM 23）、macOS 与 Windows（LLVM 23），各在 dev 与 release 配置下，另有 node 下的 wasm32——每一行的固定哈希都相同。

## 许可

封装为 Apache-2.0（mcpp-community）。ACL 为 MIT，© 2017 Nicholas Frechette & Animation Compression Library
contributors；RTM 为 MIT，© 2018 Nicholas Frechette。上游的 README 与许可证保存在 `upstream/acl/` 与 `upstream/rtm/`，
并随程序的许可证一起部署。来源记录：`upstream/documents.json`。
