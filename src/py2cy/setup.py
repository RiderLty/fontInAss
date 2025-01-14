import platform
from pathlib import Path
from setuptools import setup, Extension
from Cython.Build import cythonize

file_dir = Path(__file__).parent

extensions = [
    Extension(
        "c_utils",  # 模块名
        [(file_dir / "c_utils.pyx").as_posix()],  # 源文件路径
    )
]

ext_modules = cythonize(extensions)

if platform.system() == "Windows":
    # Windows 上生成 .pyd 文件
    ext_modules[0].ext_suffix = ".pyd"
elif platform.system() in ["Linux", "Darwin"]:
    # Linux 或 macOS 上生成 .so 文件
    ext_modules[0].ext_suffix = ".so"

setup(
    ext_modules=ext_modules,
    script_args=["build_ext",  "--build-lib",  file_dir.as_posix()],
)

# 命令行运行 python src/py2cy/setup.py
