#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "BagPlotViewsAndFilters::BagPlotViewsAndFiltersBagPlot" for configuration "Release"
set_property(TARGET BagPlotViewsAndFilters::BagPlotViewsAndFiltersBagPlot APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(BagPlotViewsAndFilters::BagPlotViewsAndFiltersBagPlot PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "ParaView::VTKExtensionsFiltersRendering;ParaView::VTKExtensionsFiltersStatistics;ParaView::VTKExtensionsMisc;VTK::FiltersExtraction;VTK::FiltersStatistics;VTK::InfovisCore"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/BagPlotViewsAndFilters/libvtkBagPlotViewsAndFiltersBagPlot.so"
  IMPORTED_SONAME_RELEASE "libvtkBagPlotViewsAndFiltersBagPlot.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS BagPlotViewsAndFilters::BagPlotViewsAndFiltersBagPlot )
list(APPEND _IMPORT_CHECK_FILES_FOR_BagPlotViewsAndFilters::BagPlotViewsAndFiltersBagPlot "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/BagPlotViewsAndFilters/libvtkBagPlotViewsAndFiltersBagPlot.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
