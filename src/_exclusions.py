"""Exclusion lists used by generate_wrapper.py.

Pulled out of the main script to keep generate_wrapper.py focused on logic
rather than data. Edit a list here when a new header / typedef / template /
class needs to be skipped or wrapped specially.
"""

# occt-800: classes that SWIG actually wraps via %include in NCollection.i.
# The generator must NOT emit a @classnotwrapped placeholder for them, since
# the placeholder would shadow the SWIG-wrapped class and hide its methods
# (e.g. NCollection_BaseList::Size, IsEmpty, Length).
NCOLLECTION_WRAPPED_CLASSES = {
    "NCollection_Array1",
    "NCollection_Array2",
    "NCollection_BaseList",
    "NCollection_BaseMap",
    "NCollection_DataMap",
    "NCollection_DoubleMap",
    "NCollection_HArray1",
    "NCollection_HArray2",
    "NCollection_HSequence",
    "NCollection_IndexedDataMap",
    "NCollection_IndexedMap",
    "NCollection_List",
    "NCollection_Map",
    "NCollection_Sequence",
    "NCollection_TListIterator",
    "NCollection_UBTree",
    "NCollection_UBTreeFiller",
    "NCollection_Vector",
    "NCollection_DynamicArray",
}


HXX_TO_EXCLUDE_FROM_CPPPARSER = [
    "Standard_CLocaleSentry.hxx",
    "IntWalk_PWalking.hxx",
    "Standard_Dump.hxx",  # to avoid a dependency of Standard over TCollection
    "IMeshData_ParametersListArrayAdaptor.hxx",
    "BRepExtrema_ProximityValueTool.hxx",  # occt-771, file cannot be parsed
    "Units_Operators.hxx",  # occt-790, create weird operators overloading in the python module
    "NCollection_ForwardRange.hxx",  # occt-800, C++17 SFINAE templates not handled by CppHeaderParser
    # occt-800: deprecated headers that #include a removed header (BOPDS_ListOfPaveBlock,
    # Graphic3d_MapOfStructure, TObj_SequenceOfObject) - their typedefs reference types
    # that no longer exist in the install
    "BOPDS_DataMapOfIntegerListOfPaveBlock.hxx",
    "BOPDS_DataMapOfPaveBlockListOfPaveBlock.hxx",
    "BOPDS_IndexedDataMapOfPaveBlockListOfPaveBlock.hxx",
    "BOPDS_VectorOfListOfPaveBlock.hxx",
    "Graphic3d_MapIteratorOfMapOfStructure.hxx",
    "TObj_Container.hxx",
]

# some includes fail at being compiled
HXX_TO_EXCLUDE_FROM_BEING_INCLUDED = [
    # report the 3 following to upstream, buggy
    # error: ‘ChFiDS_ChamfMode’ does not name a type;
    "ChFiKPart_ComputeData_ChPlnPln.hxx",
    "ChFiKPart_ComputeData_ChPlnCyl.hxx",
    "ChFiKPart_ComputeData_ChPlnCon.hxx",
    # others
    "IntWalk_PWalking.hxx",
    "IMeshData_ParametersListArrayAdaptor.hxx",
    "Standard_MemoryUtils.hxx",
    "math_VectorBase.hxx",
    "StepToTopoDS_Builder.hxx",
    "NCollection_ForwardRange.hxx",  # occt-800, C++17 SFINAE templates
    # occt-800: deprecated headers that #include a removed header
    "Graphic3d_MapIteratorOfMapOfStructure.hxx",
    "BOPDS_DataMapOfIntegerListOfPaveBlock.hxx",
    "BOPDS_DataMapOfPaveBlockListOfPaveBlock.hxx",
    "BOPDS_IndexedDataMapOfPaveBlockListOfPaveBlock.hxx",
    "BOPDS_VectorOfListOfPaveBlock.hxx",
    "TObj_Container.hxx",
]

# some typedefs parsed by CppHeader can't be wrapped
# and generate SWIG syntax errors. We just forget
# about wrapping those typedefs
TYPEDEF_TO_EXCLUDE = [
    "Handle_Standard_Transient",
    "NCollection_DelMapNode",
    "BOPDS_DataMapOfPaveBlockCommonBlock",
    # BOPCol following templates are already wrapped in TColStd
    # which causes issues with SWIg
    "BOPCol_MapOfInteger",
    "BOPCol_SequenceOfReal",
    "BOPCol_DataMapOfIntegerInteger",
    "BOPCol_DataMapOfIntegerReal",
    "BOPCol_IndexedMapOfInteger",
    "BOPCol_ListOfInteger",
    "IntWalk_VectorOfWalkingData",
    "IntWalk_VectorOfInteger",
    "TopoDS_AlertWithShape",
    "gp_TrsfNLerp",
    "TopOpeBRepTool_IndexedDataMapOfSolidClassifier",
    "Graphic3d_Vec2u",
    "Graphic3d_Vec3u",
    "Graphic3d_Vec4u",
    # "Select3D_BndBox3d",
    "SelectMgr_TriangFrustums",
    "SelectMgr_TriangFrustumsIter",
    "SelectMgr_MapOfObjectSensitives",
    "Graphic3d_IndexedMapOfAddress",
    "Graphic3d_MapOfObject",
    "Storage_PArray",
    "Interface_StaticSatisfies",
    "IMeshData::ICurveArrayAdaptor",
    "Prs3d_ShapeTool",  # circular import
    "StdSelect_ViewerSelector3d",  # circular import
    "TopoDS_ListOfShape",
    "TopoDS_ListIteratorOfListOfShape",
    "NCollection_DelListNode",  # occt790
    "NCollection_DelSeqNode",
    "BRepMesh_PluginEntryType",
    "MinMaxValuesCallback",
    "TPCallBackFunc",  # in Standard
    "CallbackOnUpdate_t",
    "MoniTool_ValueInterpret",
    "MoniTool_ValueSatisfies",
    "Interface_ValueInterpret",
    "Interface_ValueSatisfies",
]

# Following are standard integer typedefs. They have to be replaced
# with int, in the function adapt_param_type
STANDARD_INTEGER_TYPEDEF = [
    "Graphic3d_ArrayFlags",
    "Graphic3d_ZLayerId",
    "MeshVS_BuilderPriority",
    "MeshVS_BuilderPriority",
    "MeshVS_DisplayModeFlags",
    "XCAFPrs_DocumentExplorerFlags",
]

# enums to skip
ENUMS_TO_EXLUDE = ["ShapeMapGroup", "AllocatorType"]  # RWGtlf.i  # Standard.i

# classes that must not wrap a default constructor
NODEFAULTCTOR = [
    "IFSelect_SelectBase",
    "IFSelect_SelectControl",
    "IFSelect_SelectDeduct",
    "PCDM_RetrievalDriver",
    "MeshVS_DataSource3D",
    "AIS_Dimension",
    "Graphic3d_Layer",
    "Expr_BinaryExpression",
    "Expr_NamedExpression",
    "Expr_UnaryExpression",
    "Expr_SingleExpression",
    "Expr_SingleRelation",
    "Expr_UnaryExpression",
    "Geom_SweptSurface",
    "Geom_BoundedSurface",
    "ShapeCustom_Modification",
    "SelectMgr_CompositionFilter",
    "BRepMeshData_Wire",
    "BRepMeshData_PCurve",
    "BRepMeshData_Face",
    "BRepMeshData_Edge",
    "BRepMeshData_Curve",
    "Graphic3d_BvhCStructureSet",
    "PrsDim_Dimension",
]


TEMPLATES_TO_EXCLUDE = [
    "gp_TrsfNLerp",
    # IntPolyh templates don't work
    "IntPolyh_Array",
    # and this one also
    "NCollection_CellFilter",
    "BVH_PrimitiveSet",
    "BVH_Builder",
    "pair",  # for std::pair
    # for Graphic3d to compile
    "Graphic3d_UniformValue",
    "NCollection_Shared",
    "NCollection_Handle",
    "NCollection_DelMapNode",
    "BOPTools_BoxSet",
    "BOPTools_PairSelector",
    "BOPTools_BoxSet",
    "BOPTools_BoxSelector",
    "BOPTools_PairSelector",
    "BVH_Box",
    "Prs3d_Point",
    "OSD_StreamBuffer",  # occt762
    "TColStd_Array1OfListOfInteger",  ## occt781
    "TopTools_Array1OfListOfShape",
    "TColGeom_Array2OfBezierSurface",
    "FEmTool_AssemblyTable",
    "Extrema_Array2OfPOnCurv",
    "Extrema_Array2OfPOnCurv2d",
    "Extrema_Array2OfPOnSurf",
    "Extrema_Array2OfPOnSurfParams",
    "TopOpeBRepDS_Array1OfDataMapOfIntegerListOfInterference",
    "TopTrans_Array2OfOrientation",
    # occt-800: std::array template, SWIG would emit push_back/insert which
    # std::array doesn't support
    "Graphic3d_ArrayOfIndexedMapOfStructure",
    # occt-800: nested NCollection_DynamicArray<NCollection_DynamicArray<...>>
    "BOPDS_VectorOfVectorOfPair",
    "GccEnt_Array1OfPosition",
    "MAT2d_Array2OfConnexion",
    "StepElement_Array2OfCurveElementPurposeMember",
    "StepElement_Array2OfSurfaceElementPurpose",
    "StepElement_Array2OfSurfaceElementPurposeMember",
    # occt-800: nested template (Array1 of handle of HSequence)
    "StepElement_Array1OfHSequenceOfCurveElementPurposeMember",
    "StepElement_Array1OfHSequenceOfSurfaceElementPurposeMember",
    "StepElement_HArray1OfHSequenceOfCurveElementPurposeMember",
    "StepElement_HArray1OfHSequenceOfSurfaceElementPurposeMember",
    "StepDimTol_Array1OfGeometricToleranceModifier",
    "StepGeom_Array2OfCartesianPoint",
    "StepGeom_Array2OfSurfacePatch",
    "TFunction_Array1OfDataMapOfGUIDDriver",
    "TopoDS_ListOfShape",  # shadows TopTools_ListOfShape
    "TopoDS_ListIteratorOfListOfShape",  # shadows TopTools_ListIteratorOfListOfShape
    # occt-800: aliases of the GeomLProp templates defined in LProp; wrapping
    # them would make LProp import GeomLProp, which already imports LProp
    "LProp_CLProps3d",
    "LProp_SLProps3d",
]
