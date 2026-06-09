
#ifndef VTKGMVREADER_EXPORT_H
#define VTKGMVREADER_EXPORT_H

#ifdef VTKGMVREADER_STATIC_DEFINE
#  define VTKGMVREADER_EXPORT
#  define VTKGMVREADER_NO_EXPORT
#else
#  ifndef VTKGMVREADER_EXPORT
#    ifdef vtkGMVReader_EXPORTS
        /* We are building this library */
#      define VTKGMVREADER_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define VTKGMVREADER_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef VTKGMVREADER_NO_EXPORT
#    define VTKGMVREADER_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef VTKGMVREADER_DEPRECATED
#  define VTKGMVREADER_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef VTKGMVREADER_DEPRECATED_EXPORT
#  define VTKGMVREADER_DEPRECATED_EXPORT VTKGMVREADER_EXPORT VTKGMVREADER_DEPRECATED
#endif

#ifndef VTKGMVREADER_DEPRECATED_NO_EXPORT
#  define VTKGMVREADER_DEPRECATED_NO_EXPORT VTKGMVREADER_NO_EXPORT VTKGMVREADER_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef VTKGMVREADER_NO_DEPRECATED
#    define VTKGMVREADER_NO_DEPRECATED
#  endif
#endif

#endif /* VTKGMVREADER_EXPORT_H */
