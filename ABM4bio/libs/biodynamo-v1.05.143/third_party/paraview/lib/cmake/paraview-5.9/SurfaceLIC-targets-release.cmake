#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "SurfaceLIC::vtkSurfaceLICRepresentations" for configuration "Release"
set_property(TARGET SurfaceLIC::vtkSurfaceLICRepresentations APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(SurfaceLIC::vtkSurfaceLICRepresentations PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::RenderingCore;VTK::RenderingLICOpenGL2"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/SurfaceLIC/libvtkSurfaceLICRepresentations.so"
  IMPORTED_SONAME_RELEASE "libvtkSurfaceLICRepresentations.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS SurfaceLIC::vtkSurfaceLICRepresentations )
list(APPEND _IMPORT_CHECK_FILES_FOR_SurfaceLIC::vtkSurfaceLICRepresentations "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/SurfaceLIC/libvtkSurfaceLICRepresentations.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
