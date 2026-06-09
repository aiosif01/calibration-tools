#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "SLACTools::vtkSLACFilters" for configuration "Release"
set_property(TARGET SLACTools::vtkSLACFilters APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(SLACTools::vtkSLACFilters PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "ParaView::VTKExtensionsCore;ParaView::VTKExtensionsMisc;VTK::CommonCore;VTK::CommonDataModel;VTK::FiltersCore;VTK::FiltersSources;VTK::ParallelCore"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/SLACTools/libvtkSLACFilters.so"
  IMPORTED_SONAME_RELEASE "libvtkSLACFilters.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS SLACTools::vtkSLACFilters )
list(APPEND _IMPORT_CHECK_FILES_FOR_SLACTools::vtkSLACFilters "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/SLACTools/libvtkSLACFilters.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
