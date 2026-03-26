/*
 * posix_getdents shim for musl < 1.2.6 (Alpine 3.21).
 *
 * Claude Code's musl binary requires posix_getdents, added in musl 1.2.6.
 * Alpine 3.21 ships musl 1.2.5 which lacks this symbol. This shim provides
 * it via the getdents64 syscall directly, matching musl's own implementation.
 *
 * Compile: gcc -shared -fPIC -o /usr/lib/posix_getdents_shim.so posix_getdents_shim.c
 * Usage:   LD_PRELOAD=/usr/lib/posix_getdents_shim.so claude
 *
 * TODO: Remove when Alpine base image ships musl >= 1.2.6 (expected Alpine 3.22).
 */
#include <sys/types.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <errno.h>

ssize_t posix_getdents(int fd, void *buf, size_t bufsize, int flags)
{
    if (flags) {
        errno = EINVAL;
        return -1;
    }
    return syscall(SYS_getdents64, fd, buf, bufsize);
}
