from setuptools import setup
from Cython.Build import cythonize
import platform

# 根据平台设置扩展名
ext_modules = cythonize("c_utils.pyx")

if platform.system() == "Windows":
    # Windows 上生成 .pyd 文件
    ext_modules[0].ext_suffix = ".pyd"
elif platform.system() == "Linux" or platform.system() == "Darwin":
    # Linux 或 macOS 上生成 .so 文件
    ext_modules[0].ext_suffix = ".so"
else:
    pass

setup(
    ext_modules=ext_modules
)

#命令行运行 python setup.py build_ext --inplace
