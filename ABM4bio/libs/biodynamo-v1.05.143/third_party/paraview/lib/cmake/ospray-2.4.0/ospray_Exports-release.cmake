#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ospray::ospray" for configuration "Release"
set_property(TARGET ospray::ospray APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ospray::ospray PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libospray.so.2.4.0"
  IMPORTED_SONAME_RELEASE "libospray.so.2"
  )

list(APPEND _IMPORT_CHECK_TARGETS ospray::ospray )
list(APPEND _IMPORT_CHECK_FILES_FOR_ospray::ospray "${_IMPORT_PREFIX}/lib/libospray.so.2.4.0" )

# Import target "ospray::ospray_module_ispc" for configuration "Release"
set_property(TARGET ospray::ospray_module_ispc APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ospray::ospray_module_ispc PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libospray_module_ispc.so.2.4.0"
  IMPORTED_SONAME_RELEASE "libospray_module_ispc.so.2"
  )

list(APPEND _IMPORT_CHECK_TARGETS ospray::ospray_module_ispc )
list(APPEND _IMPORT_CHECK_FILES_FOR_ospray::ospray_module_ispc "${_IMPORT_PREFIX}/lib/libospray_module_ispc.so.2.4.0" )

# Import target "ospray::ospray_module_denoiser" for configuration "Release"
set_property(TARGET ospray::ospray_module_denoiser APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ospray::ospray_module_denoiser PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "OpenImageDenoise;ospray::ospray_module_ispc"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libospray_module_denoiser.so.2.4.0"
  IMPORTED_SONAME_RELEASE "libospray_module_denoiser.so.2"
  )

list(APPEND _IMPORT_CHECK_TARGETS ospray::ospray_module_denoiser )
list(APPEND _IMPORT_CHECK_FILES_FOR_ospray::ospray_module_denoiser "${_IMPORT_PREFIX}/lib/libospray_module_denoiser.so.2.4.0" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
