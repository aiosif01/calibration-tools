#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Datamine::DatamineReaders" for configuration "Release"
set_property(TARGET Datamine::DatamineReaders APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Datamine::DatamineReaders PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::CommonTransforms;VTK::FiltersCore"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/Datamine/libvtkDatamineReaders.so"
  IMPORTED_SONAME_RELEASE "libvtkDatamineReaders.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS Datamine::DatamineReaders )
list(APPEND _IMPORT_CHECK_FILES_FOR_Datamine::DatamineReaders "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/Datamine/libvtkDatamineReaders.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
