#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "DigitalRockPhysics::DigitalRocksFilters" for configuration "Release"
set_property(TARGET DigitalRockPhysics::DigitalRocksFilters APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(DigitalRockPhysics::DigitalRocksFilters PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::ParallelCore"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/DigitalRockPhysics/libvtkDigitalRocksFilters.so"
  IMPORTED_SONAME_RELEASE "libvtkDigitalRocksFilters.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS DigitalRockPhysics::DigitalRocksFilters )
list(APPEND _IMPORT_CHECK_FILES_FOR_DigitalRockPhysics::DigitalRocksFilters "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/DigitalRockPhysics/libvtkDigitalRocksFilters.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
