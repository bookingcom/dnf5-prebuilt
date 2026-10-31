/* config.h for rpm 6.1.0.
 *
 * Linux values come from CMake run against glibc 2.28 (the oldest glibc
 * targeted by this repository) with:
 *   -DENABLE_NLS=OFF -DENABLE_OPENMP=OFF -DENABLE_PYTHON=OFF
 *   -DENABLE_PLUGINS=OFF -DWITH_SELINUX=OFF -DWITH_DBUS=OFF -DWITH_AUDIT=OFF
 *   -DWITH_FAPOLICYD=OFF -DWITH_READLINE=OFF -DWITH_LIBDW=OFF -DWITH_LIBELF=OFF
 *   -DWITH_SEQUOIA=ON (OpenPGP and digests both come from rpm-sequoia)
 * WITH_CAP/WITH_ACL are enabled on Linux only. macOS (14.0+) overrides follow.
 */

#define ENABLE_NDB ON
#define ENABLE_SQLITE ON

#define HAVE_BASENAME 1
#define HAVE_BZLIB_H 1
#define HAVE_DIRNAME 1
#define HAVE_FCHMODAT 1
#define HAVE_FCHOWNAT 1
#define HAVE_FSTATAT 1
#define HAVE_GETADDRINFO 1
#define HAVE_GETCWD 1
#define HAVE_GETLINE 1
#define HAVE_GETOPT_H 1
#define HAVE_ICONV 1
#define HAVE_LIMITS_H 1
#define HAVE_LINKAT 1
#define HAVE_LOCALTIME_R 1
#define HAVE_LUTIMES 1
#define HAVE_LZMA_H 1
#define HAVE_MKDIRAT 1
#define HAVE_MKFIFOAT 1
#define HAVE_MKNODAT 1
#define HAVE_MKSTEMP 1
#define HAVE_OPENAT 1
#define HAVE_PUTENV 1
#define HAVE_REALPATH 1
#define HAVE_REGCOMP 1
#define HAVE_RENAMEAT 1
#define HAVE_SETENV 1
#define HAVE_STATVFS 1
#define HAVE_STPCPY 1
#define HAVE_STPNCPY 1
#define HAVE_SYMLINKAT 1
#define HAVE_SYS_PARAM_H 1
#define HAVE_SYS_UTSNAME_H 1
#define HAVE_UNISTD_H 1
#define HAVE_UNLINKAT 1
#define HAVE_UNSETENV 1
#define HAVE_UTIMENSAT 1
#define HAVE_UTIMES 1
#define HAVE_ZSTD 1

#if defined(__linux__)
#define HAVE_FDATASYNC 1
#define HAVE_GETAUXVAL 1
#define HAVE_GLOB_ONLYDIR 1
#define HAVE_MEMPCPY 1
#define HAVE_MREMAP 1
#define HAVE_SCHED_GETAFFINITY 1
#define HAVE_SECURE_GETENV 1
#define HAVE_SYNCFS 1
#define HAVE_SYS_AUXV_H 1
#define HAVE_UNSHARE 1
#define HAVE___PROGNAME 1
#define MAJOR_IN_SYSMACROS 1
#define WITH_ACL 1
#define WITH_CAP 1
#endif

#if defined(__APPLE__)
#define HAVE_MERGESORT 1
#define HAVE_SETPROGNAME 1
#endif

#define UID_0_USER "root"
#if defined(__APPLE__)
#define GID_0_GROUP "wheel"
#else
#define GID_0_GROUP "root"
#endif
#define C_LOCALE "C.UTF-8"
#define PACKAGE "rpm"
#define VERSION "6.1.0"
#define PACKAGE_BUGREPORT "http://rpm.org"
#define RPM_VENDOR "vendor"
