
#ifndef VTKSTREAMLINES_EXPORT_H
#define VTKSTREAMLINES_EXPORT_H

#ifdef VTKSTREAMLINES_STATIC_DEFINE
#  define VTKSTREAMLINES_EXPORT
#  define VTKSTREAMLINES_NO_EXPORT
#else
#  ifndef VTKSTREAMLINES_EXPORT
#    ifdef vtkStreamLines_EXPORTS
        /* We are building this library */
#      define VTKSTREAMLINES_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define VTKSTREAMLINES_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef VTKSTREAMLINES_NO_EXPORT
#    define VTKSTREAMLINES_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef VTKSTREAMLINES_DEPRECATED
#  define VTKSTREAMLINES_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef VTKSTREAMLINES_DEPRECATED_EXPORT
#  define VTKSTREAMLINES_DEPRECATED_EXPORT VTKSTREAMLINES_EXPORT VTKSTREAMLINES_DEPRECATED
#endif

#ifndef VTKSTREAMLINES_DEPRECATED_NO_EXPORT
#  define VTKSTREAMLINES_DEPRECATED_NO_EXPORT VTKSTREAMLINES_NO_EXPORT VTKSTREAMLINES_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef VTKSTREAMLINES_NO_DEPRECATED
#    define VTKSTREAMLINES_NO_DEPRECATED
#  endif
#endif

#endif /* VTKSTREAMLINES_EXPORT_H */
