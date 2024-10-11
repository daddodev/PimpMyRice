# Maintainer: daddodev
pkgname=python-pimpmyrice
provides=("pimpmyrice")
conflicts=("pimpmyrice")
pkgdesc=""
url="https://github.com/daddodev/pimpmyrice"
pkgver=0.0.1
pkgrel=1
arch=("any")
license=("MIT")
depends=(
    "git"
    "python>=3.11"
    "python-setuptools"
    "python-requests"
    "python-psutil"
    "python-docopt"
    "python-rich"
    "python-jinja"
    "python-colour"
    "python-pyyaml"
    "python-scikit-learn"
    "python-opencv"
    "python-fastapi"
    "uvicorn"
    "python-watchdog"
)
source=("git+https://github.com/daddodev/pimpmyrice.git")
md5sums=("SKIP")

package()
{
  cd pimpmyrice
  python setup.py install --root="$pkgdir"
}
