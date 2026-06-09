#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "catalyst::conduit" for configuration "Release"
set_property(TARGET catalyst::conduit APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(catalyst::conduit PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libconduit_catalyst2.0.a"
  )

list(APPEND _IMPORT_CHECK_TARGETS catalyst::conduit )
list(APPEND _IMPORT_CHECK_FILES_FOR_catalyst::conduit "${_IMPORT_PREFIX}/lib/libconduit_catalyst2.0.a" )

# Import target "catalyst::blueprint" for configuration "Release"
set_property(TARGET catalyst::blueprint APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(catalyst::blueprint PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libblueprint_catalyst2.0.a"
  )

list(APPEND _IMPORT_CHECK_TARGETS catalyst::blueprint )
list(APPEND _IMPORT_CHECK_FILES_FOR_catalyst::blueprint "${_IMPORT_PREFIX}/lib/libblueprint_catalyst2.0.a" )

# Import target "catalyst::libyaml" for configuration "Release"
set_property(TARGET catalyst::libyaml APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(catalyst::libyaml PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "C"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/liblibyaml_catalyst2.0.a"
  )

list(APPEND _IMPORT_CHECK_TARGETS catalyst::libyaml )
list(APPEND _IMPORT_CHECK_FILES_FOR_catalyst::libyaml "${_IMPORT_PREFIX}/lib/liblibyaml_catalyst2.0.a" )

# Import target "catalyst::b64" for configuration "Release"
set_property(TARGET catalyst::b64 APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(catalyst::b64 PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libb64_catalyst2.0.a"
  )

list(APPEND _IMPORT_CHECK_TARGETS catalyst::b64 )
list(APPEND _IMPORT_CHECK_FILES_FOR_catalyst::b64 "${_IMPORT_PREFIX}/lib/libb64_catalyst2.0.a" )

# Import target "catalyst::catalyst" for configuration "Release"
set_property(TARGET catalyst::catalyst APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(catalyst::catalyst PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "ParaView::InSitu;ParaView::VTKExtensionsCore;ParaView::VTKExtensionsConduit;ParaView::RemotingServerManager;VTK::ParallelMPI;Python3::Python"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libcatalyst.so.2"
  IMPORTED_SONAME_RELEASE "libcatalyst.so.2"
  )

list(APPEND _IMPORT_CHECK_TARGETS catalyst::catalyst )
list(APPEND _IMPORT_CHECK_FILES_FOR_catalyst::catalyst "${_IMPORT_PREFIX}/lib/libcatalyst.so.2" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
