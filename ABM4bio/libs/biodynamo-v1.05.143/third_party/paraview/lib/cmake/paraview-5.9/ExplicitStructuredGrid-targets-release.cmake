#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ExplicitStructuredGrid::vtkExplicitStructuredGrid" for configuration "Release"
set_property(TARGET ExplicitStructuredGrid::vtkExplicitStructuredGrid APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ExplicitStructuredGrid::vtkExplicitStructuredGrid PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonDataModel;VTK::CommonCore;VTK::ParallelCore;VTK::WrappingPythonCore;VTK::PythonInterpreter"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ExplicitStructuredGrid/libvtkExplicitStructuredGrid.so"
  IMPORTED_SONAME_RELEASE "libvtkExplicitStructuredGrid.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS ExplicitStructuredGrid::vtkExplicitStructuredGrid )
list(APPEND _IMPORT_CHECK_FILES_FOR_ExplicitStructuredGrid::vtkExplicitStructuredGrid "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ExplicitStructuredGrid/libvtkExplicitStructuredGrid.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
