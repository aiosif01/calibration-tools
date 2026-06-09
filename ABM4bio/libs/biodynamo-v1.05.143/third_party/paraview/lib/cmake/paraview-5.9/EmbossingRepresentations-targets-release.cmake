#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "EmbossingRepresentations::vtkEmbossingRepresentations" for configuration "Release"
set_property(TARGET EmbossingRepresentations::vtkEmbossingRepresentations APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(EmbossingRepresentations::vtkEmbossingRepresentations PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::FiltersCore;VTK::ParallelCore;VTK::RenderingCore;VTK::glew"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/EmbossingRepresentations/libvtkEmbossingRepresentations.so"
  IMPORTED_SONAME_RELEASE "libvtkEmbossingRepresentations.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS EmbossingRepresentations::vtkEmbossingRepresentations )
list(APPEND _IMPORT_CHECK_FILES_FOR_EmbossingRepresentations::vtkEmbossingRepresentations "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/EmbossingRepresentations/libvtkEmbossingRepresentations.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
