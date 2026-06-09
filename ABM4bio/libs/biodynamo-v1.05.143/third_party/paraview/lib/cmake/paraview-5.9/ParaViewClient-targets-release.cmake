#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ParaView::paraview" for configuration "Release"
set_property(TARGET ParaView::paraview APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ParaView::paraview PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/paraview"
  )

list(APPEND _IMPORT_CHECK_TARGETS ParaView::paraview )
list(APPEND _IMPORT_CHECK_FILES_FOR_ParaView::paraview "${_IMPORT_PREFIX}/bin/paraview" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
