#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ParFlow::IO" for configuration "Release"
set_property(TARGET ParFlow::IO APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ParFlow::IO PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ParFlow/libvtkParFlowIO.so"
  IMPORTED_SONAME_RELEASE "libvtkParFlowIO.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS ParFlow::IO )
list(APPEND _IMPORT_CHECK_FILES_FOR_ParFlow::IO "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ParFlow/libvtkParFlowIO.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
