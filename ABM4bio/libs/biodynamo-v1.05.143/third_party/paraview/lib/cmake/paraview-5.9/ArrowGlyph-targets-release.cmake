#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ArrowGlyph::ArrowGlyphFilter" for configuration "Release"
set_property(TARGET ArrowGlyph::ArrowGlyphFilter APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ArrowGlyph::ArrowGlyphFilter PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "ParaView::RemotingCore;VTK::CommonDataModel;VTK::FiltersCore;VTK::FiltersSources"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ArrowGlyph/libvtkArrowGlyphFilter.so"
  IMPORTED_SONAME_RELEASE "libvtkArrowGlyphFilter.so"
  )

list(APPEND _IMPORT_CHECK_TARGETS ArrowGlyph::ArrowGlyphFilter )
list(APPEND _IMPORT_CHECK_FILES_FOR_ArrowGlyph::ArrowGlyphFilter "${_IMPORT_PREFIX}/lib/paraview-5.9/plugins/ArrowGlyph/libvtkArrowGlyphFilter.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
