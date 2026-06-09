#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "HyperTreeGridFilters" for configuration "Release"
set_property(TARGET HyperTreeGridFilters APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(HyperTreeGridFilters PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonSystem"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/HyperTreeGridADR/libvtkFiltersHyperTreeGridADR.so"
  IMPORTED_SONAME_RELEASE "libvtkFiltersHyperTreeGridADR.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS HyperTreeGridFilters )
list(APPEND _IMPORT_CHECK_FILES_FOR_HyperTreeGridFilters "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/HyperTreeGridADR/libvtkFiltersHyperTreeGridADR.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
