#!/bin/bash

################################################################################
# macOS R 包编译环境快速修复脚本
# 适用于: macOS Big Sur 及以上 + Apple Silicon / Intel
# 更新日期: 2026-02-16
################################################################################

set -e  # 遇到错误立即退出

echo "=================================================="
echo "macOS R 包编译环境自动配置脚本"
echo "=================================================="
echo ""

# 检测芯片架构
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    echo "✓ 检测到 Apple Silicon (ARM64) 芯片"
    HOMEBREW_PREFIX="/opt/homebrew"
    ARCH_TYPE="Apple Silicon"
elif [ "$ARCH" = "x86_64" ]; then
    echo "✓ 检测到 Intel (x86_64) 芯片"
    HOMEBREW_PREFIX="/usr/local"
    ARCH_TYPE="Intel"
else
    echo "✗ 未知架构: $ARCH"
    exit 1
fi

echo ""
echo "=================================================="
echo "步骤 1: 检查 Xcode Command Line Tools"
echo "=================================================="

if xcode-select -p &> /dev/null; then
    echo "✓ Xcode Command Line Tools 已安装"
    XCODE_PATH=$(xcode-select -p)
    echo "  路径: $XCODE_PATH"
else
    echo "✗ Xcode Command Line Tools 未安装"
    echo "正在安装..."
    xcode-select --install
    echo "请在弹出窗口中完成安装，然后重新运行此脚本"
    exit 0
fi

echo ""
echo "=================================================="
echo "步骤 2: 检查 Homebrew"
echo "=================================================="

if command -v brew &> /dev/null; then
    BREW_PATH=$(which brew)
    echo "✓ Homebrew 已安装"
    echo "  路径: $BREW_PATH"
    
    # 验证 Homebrew 路径是否正确
    if [ "$ARCH" = "arm64" ] && [[ "$BREW_PATH" != "/opt/homebrew"* ]]; then
        echo "⚠️  警告: 您在 Apple Silicon 上使用的是 Intel 版本的 Homebrew"
        echo "  建议卸载并重新安装正确版本"
        read -p "是否现在修复? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)"
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
    fi
else
    echo "✗ Homebrew 未安装"
    echo "正在安装 Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

echo ""
echo "=================================================="
echo "步骤 3: 更新 Homebrew"
echo "=================================================="

brew update
brew upgrade

echo ""
echo "=================================================="
echo "步骤 4: 安装编译器和系统库"
echo "=================================================="

PACKAGES=(
    "gcc"                # 包含 gfortran
    "harfbuzz"          # textshaping 依赖
    "fribidi"           # textshaping 依赖
    "libgit2"           # gert 依赖
    "freetype"          # 字体渲染
    "libomp"            # OpenMP 支持
    "libxml2"           # XML 解析
    "openssl"           # SSL/TLS
    "gdal"              # 地理数据
    "geos"              # 几何引擎
    "proj"              # 投影库
    "udunits"           # 单位转换
    "libjpeg"           # JPEG 图像
    "libpng"            # PNG 图像
    "libtiff"           # TIFF 图像
    "suite-sparse"      # 稀疏矩阵（igraph 需要）
)

echo "正在安装以下包:"
for pkg in "${PACKAGES[@]}"; do
    echo "  - $pkg"
done
echo ""

for pkg in "${PACKAGES[@]}"; do
    if brew list "$pkg" &>/dev/null; then
        echo "✓ $pkg 已安装，正在升级..."
        brew upgrade "$pkg" 2>/dev/null || echo "  (已是最新版本)"
    else
        echo "→ 安装 $pkg..."
        brew install "$pkg"
    fi
done

echo ""
echo "=================================================="
echo "步骤 5: 验证 gfortran"
echo "=================================================="

# 查找 gfortran 版本
GFORTRAN_VERSIONS=$(ls $HOMEBREW_PREFIX/bin/gfortran-* 2>/dev/null | xargs -n1 basename | sed 's/gfortran-//')

if [ -z "$GFORTRAN_VERSIONS" ]; then
    echo "✗ 未找到 gfortran，尝试重新安装 gcc..."
    brew reinstall gcc
    GFORTRAN_VERSIONS=$(ls $HOMEBREW_PREFIX/bin/gfortran-* 2>/dev/null | xargs -n1 basename | sed 's/gfortran-//')
fi

echo "找到以下 gfortran 版本:"
echo "$GFORTRAN_VERSIONS"

# 获取最新版本
GNU_VER=$(echo "$GFORTRAN_VERSIONS" | sort -V | tail -1)
echo ""
echo "将使用 gfortran-$GNU_VER"

# 创建符号链接
if [ ! -L "$HOMEBREW_PREFIX/bin/gfortran" ]; then
    echo "创建 gfortran 符号链接..."
    ln -sf "$HOMEBREW_PREFIX/bin/gfortran-$GNU_VER" "$HOMEBREW_PREFIX/bin/gfortran"
fi

# 验证
if command -v gfortran &> /dev/null; then
    echo "✓ gfortran 可用"
    gfortran --version | head -1
else
    echo "✗ gfortran 不可用，请检查 PATH"
    exit 1
fi

echo ""
echo "=================================================="
echo "步骤 6: 配置 Shell PATH"
echo "=================================================="

SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "/bin/bash" ]; then
    SHELL_RC="$HOME/.bash_profile"
fi

if [ -n "$SHELL_RC" ]; then
    echo "正在配置 $SHELL_RC..."
    
    # 检查 PATH 配置是否存在
    if ! grep -q "$HOMEBREW_PREFIX/bin" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# Homebrew PATH (added by R setup script)" >> "$SHELL_RC"
        echo "export PATH=\"$HOMEBREW_PREFIX/bin:\$PATH\"" >> "$SHELL_RC"
        echo "✓ 已添加 PATH 配置到 $SHELL_RC"
    else
        echo "✓ PATH 配置已存在"
    fi
fi

echo ""
echo "=================================================="
echo "步骤 7: 创建 R Makevars 配置文件"
echo "=================================================="

mkdir -p ~/.R

MAKEVARS_FILE="$HOME/.R/Makevars"

# 获取 SDK 路径
SDKROOT=$(xcrun --show-sdk-path)

echo "正在创建 $MAKEVARS_FILE..."

cat > "$MAKEVARS_FILE" << EOF
# ============================================
# Makevars for $ARCH_TYPE
# Auto-generated on $(date)
# ============================================

# GNU 版本号
GNU_VER=$GNU_VER

# Homebrew 路径
HB=$HOMEBREW_PREFIX/bin
HO=$HOMEBREW_PREFIX/opt
HL=$HOMEBREW_PREFIX/lib
HI=$HOMEBREW_PREFIX/include

# macOS SDK 路径
SDKROOT=$SDKROOT

# Fortran 编译器
FC=\$(HB)/gfortran-\$(GNU_VER)
F77=\$(FC)
FLIBS=-L\$(HL)/gcc/\$(GNU_VER) -lgfortran -lquadmath -lm

# C/C++ 编译器
CC=clang
CXX=clang++
CXX11=clang++
CXX14=clang++
CXX17=clang++
CXX20=clang++

# 编译标志
CFLAGS=-isysroot \$(SDKROOT) -I\$(HI)
CPPFLAGS=-isysroot \$(SDKROOT) -I\$(HI)
CXXFLAGS=-isysroot \$(SDKROOT) -I\$(HI)

# 链接器标志
LDFLAGS=-L\$(HL) -L\$(HO)/libomp/lib -lomp

# OpenMP 支持
CPPFLAGS+=-Xclang -fopenmp
CPPFLAGS+=-I\$(HO)/libomp/include

# pkg-config 路径
PKG_CONFIG_PATH=\$(HO)/libxml2/lib/pkgconfig:\$(HO)/openssl@3/lib/pkgconfig

# 优化标志
CFLAGS+=-O2 -Wall
CXXFLAGS+=-O2 -Wall
FFLAGS=-O2 -Wall
FCFLAGS=-O2 -Wall

# 并行编译
MAKE=make -j4
EOF

echo "✓ Makevars 文件已创建"

echo ""
echo "=================================================="
echo "步骤 8: 创建 .Renviron 配置文件"
echo "=================================================="

RENVIRON_FILE="$HOME/.Renviron"

cat > "$RENVIRON_FILE" << EOF
# R 环境配置 (Auto-generated on $(date))
PATH="$HOMEBREW_PREFIX/bin:/usr/local/bin:\$PATH"
R_LIBS_USER="~/R/library/%p/%v"
EOF

echo "✓ .Renviron 文件已创建"

echo ""
echo "=================================================="
echo "步骤 9: 验证配置"
echo "=================================================="

echo ""
echo "编译器版本:"
echo "----------------------------------------"
echo "GCC: $(gcc --version | head -1)"
echo "gfortran: $(gfortran --version | head -1)"
echo "clang: $(clang --version | head -1)"

echo ""
echo "关键库检查:"
echo "----------------------------------------"

check_lib() {
    if pkg-config --exists "$1" 2>/dev/null; then
        echo "✓ $1: $(pkg-config --modversion $1 2>/dev/null)"
    else
        echo "✗ $1: 未找到"
    fi
}

check_lib "harfbuzz"
check_lib "fribidi"
check_lib "freetype2"
check_lib "libgit2"

echo ""
echo "=================================================="
echo "配置完成！"
echo "=================================================="
echo ""
echo "下一步操作:"
echo ""
echo "1. 重启终端或运行: source $SHELL_RC"
echo ""
echo "2. 在 R 中测试安装关键包:"
echo ""
echo "   R"
echo '   > install.packages("mvtnorm", type = "source")'
echo '   > install.packages("igraph")'
echo '   > install.packages("textshaping", type = "source")'
echo '   > install.packages("gert", type = "source")'
echo ""
echo "3. 如果遇到问题，查看日志文件:"
echo "   - ~/.R/Makevars (R 编译配置)"
echo "   - ~/.Renviron (R 环境变量)"
echo ""
echo "4. 批量安装失败的包:"
echo ""
echo '   failed_packages <- c("deldir", "mvtnorm", "statmod", "igraph",'
echo '                         "lmtest", "SparseM", "textshaping", "gert")'
echo '   install.packages(failed_packages)'
echo ""
echo "=================================================="
echo "脚本执行完成 ✓"
echo "=================================================="
