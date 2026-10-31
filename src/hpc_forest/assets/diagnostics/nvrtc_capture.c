/* Diagnostic-only NVRTC interposer. Forward the original arguments unchanged.
 * No CUDA headers, compiler-option injection, kernel edits or official timing.
 * Capture failures never alter the compiler's return value. Linux/POSIX only.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef void *Program;
typedef int (*Compile)(Program, int, const char *const *);
typedef int (*Size)(Program, size_t *);
typedef int (*Get)(Program, char *);
static _Atomic unsigned long sequence = 0;

static FILE *output(const char *stem, const char *suffix) {
    char path[4096];
    if (snprintf(path, sizeof(path), "%s.%s", stem, suffix) >= (int)sizeof(path)) return NULL;
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (fd < 0) return NULL;
    FILE *f = fdopen(fd, "wb");
    if (!f) close(fd);
    return f;
}

static void json_string(FILE *f, const char *s) {
    fputc('"', f);
    for (const unsigned char *p = (const unsigned char *)s; *p; ++p) {
        if (*p == '"' || *p == '\\') fprintf(f, "\\%c", *p);
        else if (*p < 32 || *p >= 127) fprintf(f, "\\u%04x", *p);
        else fputc(*p, f);
    }
    fputc('"', f);
}

static int capture(Program program, const char *stem, const char *suffix,
                   const char *size_name, const char *get_name) {
    Size size_fn = (Size)dlsym(RTLD_NEXT, size_name);
    Get get_fn = (Get)dlsym(RTLD_NEXT, get_name);
    size_t length = 0;
    if (!size_fn || !get_fn || size_fn(program, &length) || !length || length > 16777216) return 0;
    char *bytes = malloc(length);
    if (!bytes) return 0;
    int saved = 0;
    if (!get_fn(program, bytes)) {
        FILE *f = output(stem, suffix);
        if (f) { saved = fwrite(bytes, 1, length, f) == length; if (fclose(f)) saved = 0; }
    }
    free(bytes);
    return saved;
}

int nvrtcCompileProgram(Program program, int count, const char *const *options) {
    Compile compile = (Compile)dlsym(RTLD_NEXT, "nvrtcCompileProgram");
    if (!compile) return 11; /* NVRTC_ERROR_INTERNAL_ERROR: broken dynamic linkage. */
    int status = compile(program, count, options);
    const char *directory = getenv("FOREST_NVRTC_CAPTURE");
    if (!directory || count < 0 || count > 4096) return status;
    char stem[4000];
    unsigned long index = atomic_fetch_add(&sequence, 1);
    if (snprintf(stem, sizeof(stem), "%s/%ld-%lu", directory, (long)getpid(), index) >= (int)sizeof(stem)) return status;
    int log = capture(program, stem, "log", "nvrtcGetProgramLogSize", "nvrtcGetProgramLog");
    int cubin = status == 0 && capture(program, stem, "cubin", "nvrtcGetCUBINSize", "nvrtcGetCUBIN");
    int ptx = status == 0 && capture(program, stem, "ptx", "nvrtcGetPTXSize", "nvrtcGetPTX");
    FILE *f = output(stem, "json");
    if (f) {
        Dl_info library = {0};
        dladdr((void *)compile, &library);
        fprintf(f, "{\"status\":%d,\"options_unchanged\":true,\"options\":[", status);
        for (int i = 0; i < count; ++i) { if (i) fputc(',', f); json_string(f, options[i]); }
        fputs("],\"library\":", f);
        json_string(f, library.dli_fname ? library.dli_fname : "unknown");
        fprintf(f, ",\"log_captured\":%s,\"cubin_captured\":%s,\"ptx_captured\":%s}\n",
                log ? "true" : "false", cubin ? "true" : "false", ptx ? "true" : "false");
        fclose(f);
    }
    return status;
}
