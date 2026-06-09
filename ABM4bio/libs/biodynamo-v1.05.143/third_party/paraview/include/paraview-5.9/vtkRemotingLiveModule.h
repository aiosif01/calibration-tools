
#ifndef VTKREMOTINGLIVE_EXPORT_H
#define VTKREMOTINGLIVE_EXPORT_H

#ifdef VTKREMOTINGLIVE_STATIC_DEFINE
#  define VTKREMOTINGLIVE_EXPORT
#  define VTKREMOTINGLIVE_NO_EXPORT
#else
#  ifndef VTKREMOTINGLIVE_EXPORT
#    ifdef RemotingLive_EXPORTS
        /* We are building this library */
#      define VTKREMOTINGLIVE_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define VTKREMOTINGLIVE_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef VTKREMOTINGLIVE_NO_EXPORT
#    define VTKREMOTINGLIVE_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef VTKREMOTINGLIVE_DEPRECATED
#  define VTKREMOTINGLIVE_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef VTKREMOTINGLIVE_DEPRECATED_EXPORT
#  define VTKREMOTINGLIVE_DEPRECATED_EXPORT VTKREMOTINGLIVE_EXPORT VTKREMOTINGLIVE_DEPRECATED
#endif

#ifndef VTKREMOTINGLIVE_DEPRECATED_NO_EXPORT
#  define VTKREMOTINGLIVE_DEPRECATED_NO_EXPORT VTKREMOTINGLIVE_NO_EXPORT VTKREMOTINGLIVE_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef VTKREMOTINGLIVE_NO_DEPRECATED
#    define VTKREMOTINGLIVE_NO_DEPRECATED
#  endif
#endif

#endif /* VTKREMOTINGLIVE_EXPORT_H */
