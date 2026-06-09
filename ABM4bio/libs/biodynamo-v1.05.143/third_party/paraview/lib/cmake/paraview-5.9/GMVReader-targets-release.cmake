#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "GMVReader::vtkGMVReader" for configuration "Release"
set_property(TARGET GMVReader::vtkGMVReader APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(GMVReader::vtkGMVReader PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::CommonMisc;VTK::ParallelCore"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GMVReader/libvtkGMVReader.so"
  IMPORTED_SONAME_RELEASE "libvtkGMVReader.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS GMVReader::vtkGMVReader )
list(APPEND _IMPORT_CHECK_FILES_FOR_GMVReader::vtkGMVReader "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GMVReader/libvtkGMVReader.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
