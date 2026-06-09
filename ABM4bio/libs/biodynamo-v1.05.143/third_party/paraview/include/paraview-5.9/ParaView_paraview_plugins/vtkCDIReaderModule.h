
#ifndef VTKCDIREADER_EXPORT_H
#define VTKCDIREADER_EXPORT_H

#ifdef VTKCDIREADER_STATIC_DEFINE
#  define VTKCDIREADER_EXPORT
#  define VTKCDIREADER_NO_EXPORT
#else
#  ifndef VTKCDIREADER_EXPORT
#    ifdef vtkCDIReader_EXPORTS
        /* We are building this library */
#      define VTKCDIREADER_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define VTKCDIREADER_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef VTKCDIREADER_NO_EXPORT
#    define VTKCDIREADER_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef VTKCDIREADER_DEPRECATED
#  define VTKCDIREADER_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef VTKCDIREADER_DEPRECATED_EXPORT
#  define VTKCDIREADER_DEPRECATED_EXPORT VTKCDIREADER_EXPORT VTKCDIREADER_DEPRECATED
#endif

#ifndef VTKCDIREADER_DEPRECATED_NO_EXPORT
#  define VTKCDIREADER_DEPRECATED_NO_EXPORT VTKCDIREADER_NO_EXPORT VTKCDIREADER_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef VTKCDIREADER_NO_DEPRECATED
#    define VTKCDIREADER_NO_DEPRECATED
#  endif
#endif

#endif /* VTKCDIREADER_EXPORT_H */
