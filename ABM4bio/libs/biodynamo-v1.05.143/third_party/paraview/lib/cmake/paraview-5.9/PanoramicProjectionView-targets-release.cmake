#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "PanoramicProjectionView::vtkPanoramicProjectionViews" for configuration "Release"
set_property(TARGET PanoramicProjectionView::vtkPanoramicProjectionViews APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(PanoramicProjectionView::vtkPanoramicProjectionViews PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::RenderingCore"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/PanoramicProjectionView/libvtkPanoramicProjectionViews.so"
  IMPORTED_SONAME_RELEASE "libvtkPanoramicProjectionViews.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS PanoramicProjectionView::vtkPanoramicProjectionViews )
list(APPEND _IMPORT_CHECK_FILES_FOR_PanoramicProjectionView::vtkPanoramicProjectionViews "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/PanoramicProjectionView/libvtkPanoramicProjectionViews.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
