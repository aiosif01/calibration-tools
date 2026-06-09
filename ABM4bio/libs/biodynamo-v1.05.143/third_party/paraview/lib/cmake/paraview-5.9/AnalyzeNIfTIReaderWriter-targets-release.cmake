#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "AnalyzeNIfTIIO::NIfTIIO" for configuration "Release"
set_property(TARGET AnalyzeNIfTIIO::NIfTIIO APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(AnalyzeNIfTIIO::NIfTIIO PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "VTK::CommonCore;VTK::CommonDataModel;VTK::zlib"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/AnalyzeNIfTIReaderWriter/libvtkAnalyzeNIfTIIO.so"
  IMPORTED_SONAME_RELEASE "libvtkAnalyzeNIfTIIO.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS AnalyzeNIfTIIO::NIfTIIO )
list(APPEND _IMPORT_CHECK_FILES_FOR_AnalyzeNIfTIIO::NIfTIIO "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/AnalyzeNIfTIReaderWriter/libvtkAnalyzeNIfTIIO.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
