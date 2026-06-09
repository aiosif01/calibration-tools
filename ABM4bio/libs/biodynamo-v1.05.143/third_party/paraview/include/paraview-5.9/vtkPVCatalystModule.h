
#ifndef VTKPVCATALYST_EXPORT_H
#define VTKPVCATALYST_EXPORT_H

#ifdef VTKPVCATALYST_STATIC_DEFINE
#  define VTKPVCATALYST_EXPORT
#  define VTKPVCATALYST_NO_EXPORT
#else
#  ifndef VTKPVCATALYST_EXPORT
#    ifdef Catalyst_EXPORTS
        /* We are building this library */
#      define VTKPVCATALYST_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define VTKPVCATALYST_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef VTKPVCATALYST_NO_EXPORT
#    define VTKPVCATALYST_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef VTKPVCATALYST_DEPRECATED
#  define VTKPVCATALYST_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef VTKPVCATALYST_DEPRECATED_EXPORT
#  define VTKPVCATALYST_DEPRECATED_EXPORT VTKPVCATALYST_EXPORT VTKPVCATALYST_DEPRECATED
#endif

#ifndef VTKPVCATALYST_DEPRECATED_NO_EXPORT
#  define VTKPVCATALYST_DEPRECATED_NO_EXPORT VTKPVCATALYST_NO_EXPORT VTKPVCATALYST_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef VTKPVCATALYST_NO_DEPRECATED
#    define VTKPVCATALYST_NO_DEPRECATED
#  endif
#endif

#endif /* VTKPVCATALYST_EXPORT_H */
