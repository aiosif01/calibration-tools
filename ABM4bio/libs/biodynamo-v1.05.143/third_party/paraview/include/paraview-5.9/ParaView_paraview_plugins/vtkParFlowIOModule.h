
#ifndef VTKPARFLOWIO_EXPORT_H
#define VTKPARFLOWIO_EXPORT_H

#ifdef VTKPARFLOWIO_STATIC_DEFINE
#  define VTKPARFLOWIO_EXPORT
#  define VTKPARFLOWIO_NO_EXPORT
#else
#  ifndef VTKPARFLOWIO_EXPORT
#    ifdef IO_EXPORTS
        /* We are building this library */
#      define VTKPARFLOWIO_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define VTKPARFLOWIO_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef VTKPARFLOWIO_NO_EXPORT
#    define VTKPARFLOWIO_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef VTKPARFLOWIO_DEPRECATED
#  define VTKPARFLOWIO_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef VTKPARFLOWIO_DEPRECATED_EXPORT
#  define VTKPARFLOWIO_DEPRECATED_EXPORT VTKPARFLOWIO_EXPORT VTKPARFLOWIO_DEPRECATED
#endif

#ifndef VTKPARFLOWIO_DEPRECATED_NO_EXPORT
#  define VTKPARFLOWIO_DEPRECATED_NO_EXPORT VTKPARFLOWIO_NO_EXPORT VTKPARFLOWIO_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef VTKPARFLOWIO_NO_DEPRECATED
#    define VTKPARFLOWIO_NO_DEPRECATED
#  endif
#endif

#endif /* VTKPARFLOWIO_EXPORT_H */
