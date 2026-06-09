
#ifndef CATALYST_EXPORT_H
#define CATALYST_EXPORT_H

#ifdef CATALYST_STATIC_DEFINE
#  define CATALYST_EXPORT
#  define CATALYST_NO_EXPORT
#else
#  ifndef CATALYST_EXPORT
#    ifdef catalyst_EXPORTS
        /* We are building this library */
#      define CATALYST_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define CATALYST_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef CATALYST_NO_EXPORT
#    define CATALYST_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef CATALYST_DEPRECATED
#  define CATALYST_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef CATALYST_DEPRECATED_EXPORT
#  define CATALYST_DEPRECATED_EXPORT CATALYST_EXPORT CATALYST_DEPRECATED
#endif

#ifndef CATALYST_DEPRECATED_NO_EXPORT
#  define CATALYST_DEPRECATED_NO_EXPORT CATALYST_NO_EXPORT CATALYST_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef CATALYST_NO_DEPRECATED
#    define CATALYST_NO_DEPRECATED
#  endif
#endif

#endif /* CATALYST_EXPORT_H */
