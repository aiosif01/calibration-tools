#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ParaView::pvserver" for configuration "Release"
set_property(TARGET ParaView::pvserver APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ParaView::pvserver PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/pvserver"
  )

list(APPEND _IMPORT_CHECK_TARGETS ParaView::pvserver )
list(APPEND _IMPORT_CHECK_FILES_FOR_ParaView::pvserver "${_IMPORT_PREFIX}/bin/pvserver" )

# Import target "ParaView::pvdataserver" for configuration "Release"
set_property(TARGET ParaView::pvdataserver APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ParaView::pvdataserver PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/pvdataserver"
  )

list(APPEND _IMPORT_CHECK_TARGETS ParaView::pvdataserver )
list(APPEND _IMPORT_CHECK_FILES_FOR_ParaView::pvdataserver "${_IMPORT_PREFIX}/bin/pvdataserver" )

# Import target "ParaView::pvrenderserver" for configuration "Release"
set_property(TARGET ParaView::pvrenderserver APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ParaView::pvrenderserver PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/pvrenderserver"
  )

list(APPEND _IMPORT_CHECK_TARGETS ParaView::pvrenderserver )
list(APPEND _IMPORT_CHECK_FILES_FOR_ParaView::pvrenderserver "${_IMPORT_PREFIX}/bin/pvrenderserver" )

# Import target "ParaView::pvbatch" for configuration "Release"
set_property(TARGET ParaView::pvbatch APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ParaView::pvbatch PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/pvbatch"
  )

list(APPEND _IMPORT_CHECK_TARGETS ParaView::pvbatch )
list(APPEND _IMPORT_CHECK_FILES_FOR_ParaView::pvbatch "${_IMPORT_PREFIX}/bin/pvbatch" )

# Import target "ParaView::pvpython" for configuration "Release"
set_property(TARGET ParaView::pvpython APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ParaView::pvpython PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/pvpython"
  )

list(APPEND _IMPORT_CHECK_TARGETS ParaView::pvpython )
list(APPEND _IMPORT_CHECK_FILES_FOR_ParaView::pvpython "${_IMPORT_PREFIX}/bin/pvpython" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
