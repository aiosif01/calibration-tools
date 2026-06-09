#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "CDIReader::vtkCDIReader" for configuration "Release"
set_property(TARGET CDIReader::vtkCDIReader APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(CDIReader::vtkCDIReader PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "ParaView::VTKExtensionsIOCore;VTK::netcdf;VTK::ParallelCore;VTK::ParallelMPI"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/CDIReader/libvtkCDIReader.so"
  IMPORTED_SONAME_RELEASE "libvtkCDIReader.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS CDIReader::vtkCDIReader )
list(APPEND _IMPORT_CHECK_FILES_FOR_CDIReader::vtkCDIReader "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/CDIReader/libvtkCDIReader.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
