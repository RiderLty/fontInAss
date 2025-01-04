import platform
from pathlib import Path

from setuptools import setup
from Cython.Build import cythonize

file_dir = Path(__file__).parent

# 根据平台设置扩展名
ext_modules = cythonize((file_dir / "c_utils.pyx").as_posix())

if platform.system() == "Windows":
    # Windows 上生成 .pyd 文件
    ext_modules[0].ext_suffix = ".pyd"
elif platform.system() == "Linux" or platform.system() == "Darwin":
    # Linux 或 macOS 上生成 .so 文件
    ext_modules[0].ext_suffix = ".so"
else:
    pass

setup(
    ext_modules=ext_modules,
    script_args=["build_ext",  "--build-lib",  file_dir.as_posix()],
)

# 命令行运行 python src/py2cy/setup.py
