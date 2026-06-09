#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "GeodesicMeasurement::GeodesicMeasurementFilters" for configuration "Release"
set_property(TARGET GeodesicMeasurement::GeodesicMeasurementFilters APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(GeodesicMeasurement::GeodesicMeasurementFilters PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::FiltersCore;VTK::FiltersModeling"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GeodesicMeasurement/libvtkGeodesicMeasurementFilters.so"
  IMPORTED_SONAME_RELEASE "libvtkGeodesicMeasurementFilters.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS GeodesicMeasurement::GeodesicMeasurementFilters )
list(APPEND _IMPORT_CHECK_FILES_FOR_GeodesicMeasurement::GeodesicMeasurementFilters "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GeodesicMeasurement/libvtkGeodesicMeasurementFilters.so" )

# Import target "GeodesicMeasurement::FmmMesh" for configuration "Release"
set_property(TARGET GeodesicMeasurement::FmmMesh APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(GeodesicMeasurement::FmmMesh PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GeodesicMeasurement/libFmmMesh.a"
  )

list(APPEND _IMPORT_CHECK_TARGETS GeodesicMeasurement::FmmMesh )
list(APPEND _IMPORT_CHECK_FILES_FOR_GeodesicMeasurement::FmmMesh "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GeodesicMeasurement/libFmmMesh.a" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
