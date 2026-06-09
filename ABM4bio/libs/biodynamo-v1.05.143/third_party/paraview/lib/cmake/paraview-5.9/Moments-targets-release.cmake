#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Moments::MomentFilters" for configuration "Release"
set_property(TARGET Moments::MomentFilters APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Moments::MomentFilters PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::CommonTransforms;VTK::FiltersCore;VTK::FiltersGeneral;VTK::FiltersSources"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/Moments/libvtkMomentFilters.so"
  IMPORTED_SONAME_RELEASE "libvtkMomentFilters.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS Moments::MomentFilters )
list(APPEND _IMPORT_CHECK_FILES_FOR_Moments::MomentFilters "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/Moments/libvtkMomentFilters.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
