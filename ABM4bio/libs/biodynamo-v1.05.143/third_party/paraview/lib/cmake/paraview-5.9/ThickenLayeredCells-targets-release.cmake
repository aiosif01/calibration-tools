#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ThickenLayeredCells::vtkThickenLayeredCellsFilters" for configuration "Release"
set_property(TARGET ThickenLayeredCells::vtkThickenLayeredCellsFilters APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ThickenLayeredCells::vtkThickenLayeredCellsFilters PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ThickenLayeredCells/libvtkThickenLayeredCellsFilters.so"
  IMPORTED_SONAME_RELEASE "libvtkThickenLayeredCellsFilters.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS ThickenLayeredCells::vtkThickenLayeredCellsFilters )
list(APPEND _IMPORT_CHECK_FILES_FOR_ThickenLayeredCells::vtkThickenLayeredCellsFilters "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ThickenLayeredCells/libvtkThickenLayeredCellsFilters.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
