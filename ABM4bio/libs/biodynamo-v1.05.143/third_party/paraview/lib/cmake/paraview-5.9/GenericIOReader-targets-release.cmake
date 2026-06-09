#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "GenericIOReader::vtkGenericIOReader" for configuration "Release"
set_property(TARGET GenericIOReader::vtkGenericIOReader APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(GenericIOReader::vtkGenericIOReader PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GenericIOReader/libvtkGenericIOReader.so"
  IMPORTED_SONAME_RELEASE "libvtkGenericIOReader.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS GenericIOReader::vtkGenericIOReader )
list(APPEND _IMPORT_CHECK_FILES_FOR_GenericIOReader::vtkGenericIOReader "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GenericIOReader/libvtkGenericIOReader.so" )

# Import target "GenericIOReader::LANL_GenericIO" for configuration "Release"
set_property(TARGET GenericIOReader::LANL_GenericIO APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(GenericIOReader::LANL_GenericIO PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GenericIOReader/libLANL_GenericIO.a"
  )

list(APPEND _IMPORT_CHECK_TARGETS GenericIOReader::LANL_GenericIO )
list(APPEND _IMPORT_CHECK_FILES_FOR_GenericIOReader::LANL_GenericIO "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/GenericIOReader/libLANL_GenericIO.a" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
