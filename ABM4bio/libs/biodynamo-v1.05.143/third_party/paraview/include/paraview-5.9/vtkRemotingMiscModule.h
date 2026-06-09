
#ifndef VTKREMOTINGMISC_EXPORT_H
#define VTKREMOTINGMISC_EXPORT_H

#ifdef VTKREMOTINGMISC_STATIC_DEFINE
#  define VTKREMOTINGMISC_EXPORT
#  define VTKREMOTINGMISC_NO_EXPORT
#else
#  ifndef VTKREMOTINGMISC_EXPORT
#    ifdef RemotingMisc_EXPORTS
        /* We are building this library */
#      define VTKREMOTINGMISC_EXPORT __attribute__((visibility("default")))
#    else
        /* We are using this library */
#      define VTKREMOTINGMISC_EXPORT __attribute__((visibility("default")))
#    endif
#  endif

#  ifndef VTKREMOTINGMISC_NO_EXPORT
#    define VTKREMOTINGMISC_NO_EXPORT __attribute__((visibility("hidden")))
#  endif
#endif

#ifndef VTKREMOTINGMISC_DEPRECATED
#  define VTKREMOTINGMISC_DEPRECATED __attribute__ ((__deprecated__))
#endif

#ifndef VTKREMOTINGMISC_DEPRECATED_EXPORT
#  define VTKREMOTINGMISC_DEPRECATED_EXPORT VTKREMOTINGMISC_EXPORT VTKREMOTINGMISC_DEPRECATED
#endif

#ifndef VTKREMOTINGMISC_DEPRECATED_NO_EXPORT
#  define VTKREMOTINGMISC_DEPRECATED_NO_EXPORT VTKREMOTINGMISC_NO_EXPORT VTKREMOTINGMISC_DEPRECATED
#endif

#if 0 /* DEFINE_NO_DEPRECATED */
#  ifndef VTKREMOTINGMISC_NO_DEPRECATED
#    define VTKREMOTINGMISC_NO_DEPRECATED
#  endif
#endif

#endif /* VTKREMOTINGMISC_EXPORT_H */
