"""SWIG / pyi template strings used by generate_wrapper.py.

These constants are pure data — strings (and string.Template wrappers around
them) substituted into the generated `.i` and `.pyi` files. They live in their
own module so generate_wrapper.py can stay focused on the generation logic.
"""

from string import Template


LICENSE_HEADER = """/*
Copyright 2008-2026 Thomas Paviot (tpaviot@gmail.com)

This file is part of pythonOCC.
pythonOCC is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pythonOCC is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with pythonOCC.  If not, see <http://www.gnu.org/licenses/>.
*/
"""


##########################
# Templates for includes #
##########################

BOPDS_HEADER_TEMPLATE = """
%include "BOPCol_NCVector.hxx";
"""

INTPOLYH_HEADER_TEMPLATE = """
%include "IntPolyh_Array.hxx";
%include "IntPolyh_ArrayOfTriangles.hxx";
%include "IntPolyh_SeqOfStartPoints.hxx";
%include "IntPolyh_ArrayOfEdges.hxx";
%include "IntPolyh_ArrayOfTangentZones.hxx";
%include "IntPolyh_ArrayOfSectionLines.hxx";
%include "IntPolyh_ListOfCouples.hxx";
%include "IntPolyh_ArrayOfPoints.hxx";
"""

BVH_HEADER_TEMPLATE = """
%include "BVH_PrimitiveSet.hxx";
"""

PRS3D_HEADER_TEMPLATE = """
%include "Prs3d_Point.hxx";
"""

BREPALGOAPI_HEADER = """
%include "BRepAlgoAPI_Algo.hxx";
"""

GRAPHIC3D_DEFINE_HEADER = """
%define Handle_Graphic3d_TextureSet Handle(Graphic3d_TextureSet)
%enddef
%define Handle_Aspect_DisplayConnection Handle(Aspect_DisplayConnection)
%enddef
%define Handle_Graphic3d_NMapOfTransient Handle(Graphic3d_NMapOfTransient)
%enddef
"""

NCOLLECTION_HEADER_TEMPLATE = """
%include "Standard_Macro.hxx";
%include "Standard_DefineAlloc.hxx";
%include "NCollection_DefineAlloc.hxx";
%include "NCollection_Array1.hxx";
%include "NCollection_Array2.hxx";
%include "NCollection_BaseList.hxx";
%include "NCollection_BaseMap.hxx";
// occt-800rc5: NCollection_BasePointerVector methods are declared
// Standard_EXPORT but not exported from libTKernel.so. Skip the header
// entirely so SWIG does not emit linker references.
//%include "NCollection_BasePointerVector.hxx";
%ignore NCollection_BasePointerVector;
%include "NCollection_Map.hxx";
%include "NCollection_List.hxx";
%include "NCollection_Sequence.hxx";
%include "NCollection_DataMap.hxx";
%include "NCollection_IndexedMap.hxx";
%include "NCollection_IndexedDataMap.hxx";
%include "NCollection_DoubleMap.hxx";
// occt-800: HArray1/HArray2/HSequence are now plain template classes
// (the DEFINE_HARRAY1 / DEFINE_HSEQUENCE macros were removed). Declare
// SWIG-visible templates inheriting only from Standard_Transient so that
// %wrap_handle / %make_alias keep working without dragging the
// NCollection_Array1<T> base (which would force T to be a complete type
// in every translation unit that references the template instantiation).
template <typename TheItemType>
class NCollection_HArray1 : public Standard_Transient
{
public:
  NCollection_HArray1();
  NCollection_HArray1(const int theLower, const int theUpper);
  NCollection_HArray1(const int theLower, const int theUpper, const TheItemType& theValue);
  int Lower() const;
  int Upper() const;
  int Length() const;
  int Size() const;
  bool IsEmpty() const;
  void SetValue(const int theIndex, const TheItemType& theItem);
  const TheItemType& Value(const int theIndex) const;
  TheItemType& ChangeValue(const int theIndex);
  const TheItemType& First() const;
  const TheItemType& Last() const;
  void Init(const TheItemType& theValue);
};

template <typename TheItemType>
class NCollection_HArray2 : public Standard_Transient
{
public:
  NCollection_HArray2(const int theRowLower, const int theRowUpper,
                      const int theColLower, const int theColUpper);
  NCollection_HArray2(const int theRowLower, const int theRowUpper,
                      const int theColLower, const int theColUpper,
                      const TheItemType& theValue);
  int LowerRow() const;
  int UpperRow() const;
  int LowerCol() const;
  int UpperCol() const;
  int NbRows() const;
  int NbColumns() const;
  void SetValue(const int theRow, const int theCol, const TheItemType& theItem);
  const TheItemType& Value(const int theRow, const int theCol) const;
  TheItemType& ChangeValue(const int theRow, const int theCol);
  void Init(const TheItemType& theValue);
};

// occt-800: NCollection_PackedMap is a heavily-templated class with
// constexpr/std::conditional that SWIG cannot fully parse. Declare a
// minimal SWIG-visible shim so %template instantiations like
// `TColStd_PackedMapOfInteger = NCollection_PackedMap<int>` link and
// expose the small surface that pythonocc users actually need.
template <typename IntType>
class NCollection_PackedMap
{
public:
  NCollection_PackedMap();
  size_t Size() const;
  size_t Extent() const;
  size_t NbBuckets() const;
  bool IsEmpty() const;
  void Clear();
  bool Add(IntType theValue);
  bool Contains(IntType theValue) const;
  bool Remove(IntType theValue);
};

template <typename TheItemType>
class NCollection_HSequence : public Standard_Transient
{
public:
  NCollection_HSequence();
  int Size() const;
  int Length() const;
  bool IsEmpty() const;
  void Clear();
  void Append(const TheItemType& theItem);
  void Prepend(const TheItemType& theItem);
  void Reverse();
  const TheItemType& First() const;
  const TheItemType& Last() const;
  const TheItemType& Value(const int theIndex) const;
  void SetValue(const int theIndex, const TheItemType& theItem);
  void Remove(const int theIndex);
};
%include "NCollection_DefineAlloc.hxx";
%include "NCollection_UBTree.hxx";
%include "NCollection_UBTreeFiller.hxx";
%include "NCollection_Lerp.hxx";
%include "NCollection_Vector.hxx";
// occt-800: NCollection_DynamicArray is a new container deriving from
// NCollection_BasePointerVector. Forward-declare an empty wrapper so
// %template instantiations like NCollection_DynamicArray<X> link.
// (BasePointerVector methods are declared Standard_EXPORT but not actually
//  exported from libTKernel.so in 8.0rc5, so we cannot wrap them directly.)
template <class TheItemType>
class NCollection_DynamicArray
{
public:
  NCollection_DynamicArray();
  NCollection_DynamicArray(const size_t theIncrement);
  size_t Length() const;
  size_t Size() const;
  bool IsEmpty() const;
  void Clear();
  const TheItemType& Value(const size_t theIndex) const;
  const TheItemType& First() const;
  const TheItemType& Last() const;
  TheItemType& ChangeValue(const size_t theIndex);
  void Append(const TheItemType& theValue);
  void SetValue(const size_t theIndex, const TheItemType& theValue);
};
%include "NCollection_Vec2.hxx";
%include "NCollection_Vec3.hxx";
%include "NCollection_Vec4.hxx";
%include "NCollection_Mat4.hxx";
%include "NCollection_TListIterator.hxx";
%include "NCollection_UtfString.hxx";
%include "NCollection_UtfIterator.hxx";
%include "NCollection_SparseArray.hxx";

%ignore NCollection_List::First();
%ignore NCollection_List::Last();
%ignore NCollection_TListIterator::Value();

%ignore NCollection_Array2::Value();
%ignore NCollection_Array2::ChangeValue();
%ignore NCollection_Array2::operator();
"""

MATH_HEADER_TEMPLATE = """
%include "math_VectorBase.hxx";
%template(math_Vector) math_VectorBase<double>;
typedef math_VectorBase<double> math_Vector;
"""

HARRAY1_TEMPLATE = Template(
    """
class $HClassName : public $Array1Type, public Standard_Transient {
  public:
    $HClassName(const Standard_Integer theLower, const Standard_Integer theUpper);
    $HClassName(const Standard_Integer theLower, const Standard_Integer theUpper, const $Array1Type::value_type& theValue);
    $HClassName(const $Array1Type& theOther);
    const $Array1Type& Array1();
    $Array1Type& ChangeArray1();
};
%make_alias($HClassName)

"""
)

HARRAY1_TEMPLATE_PYI = Template(
    """
class $HClassName($Array1Type, Standard_Transient):
    def __init__(self, theLower: int, theUpper: int) -> None: ...
    def Array1(self) -> $Array1Type: ...

"""
)

HARRAY2_TEMPLATE = Template(
    """
class $HClassName : public $Array2Type, public Standard_Transient {
  public:
    $HClassName(const Standard_Integer theRowLow, const Standard_Integer theRowUpp, const Standard_Integer theColLow,
                const Standard_Integer theColUpp);
    $HClassName(const Standard_Integer theRowLow, const Standard_Integer theRowUpp, const Standard_Integer theColLow,
               const Standard_Integer theColUpp, const $Array2Type::value_type& theValue);
    $HClassName(const $Array2Type& theOther);
    const $Array2Type& Array2 ();
    $Array2Type& ChangeArray2 (); 
};
%make_alias($HClassName)

"""
)

HARRAY2_TEMPLATE_PYI = Template(
    """
class $HClassName($Array2Type, Standard_Transient):
    @overload
    def __init__(self, theRowLow: int, theRowUpp: int, theColLow: int, theColUpp: int) -> None: ...
    @overload
    def __init__(self, theOther: $Array2Type) -> None: ...
    def Array2(self) -> $Array2Type: ...

"""
)

HSEQUENCE_TEMPLATE = Template(
    """
class $HClassName : public $SequenceType, public Standard_Transient {
  public:
    $HClassName();
    $HClassName(const $SequenceType& theOther);
    const $SequenceType& Sequence();
    void Append (const $SequenceType::value_type& theItem);
    void Append ($SequenceType& theSequence);
    $SequenceType& ChangeSequence();
};
%make_alias($HClassName)

"""
)

HSEQUENCE_TEMPLATE_PYI = Template(
    """
class $HClassName($SequenceType, Standard_Transient):
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, other: $SequenceType) -> None: ...
    def Sequence(self) -> $SequenceType: ...
    def Append(self, theSequence: $SequenceType) -> None: ...

"""
)


# the related pyi stub string
NCOLLECTION_ARRAY1_EXTEND_TEMPLATE_PYI = Template(
    """
class $NCollection_Array1_Template_Instanciation:
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, theLower: int, theUpper: int) -> None: ...
    def __getitem__(self, index: int) -> $Type_T: ...
    def __setitem__(self, index: int, value: $Type_T) -> None: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[$Type_T]: ...
    def next(self) -> $Type_T: ...
    __next__ = next
    def Init(self, theValue: $Type_T) -> None: ...
    def Size(self) -> int: ...
    def Length(self) -> int: ...
    def IsEmpty(self) -> bool: ...
    def Lower(self) -> int: ...
    def Upper(self) -> int: ...
    def IsDetectable(self) -> bool: ...
    def IsAllocated(self) -> bool: ...
    def First(self) -> $Type_T: ...
    def Last(self) -> $Type_T: ...
    def Value(self, theIndex: int) -> $Type_T: ...
    def SetValue(self, theIndex: int, theValue: $Type_T) -> None: ...
"""
)

NCOLLECTION_LIST_EXTEND_TEMPLATE = Template(
    """
%extend $NCollection_List_Template_Instanciation {
    // occt-800: re-export Size/Length/IsEmpty per instantiation; the
    // NCollection_BaseList header is wrapped but its inherited methods
    // don't propagate cleanly to the typedef-aliased Python class.
    size_t Size() const noexcept { return $$self->Size(); }
    int Length() const noexcept { return $$self->Length(); }
    bool IsEmpty() const noexcept { return $$self->IsEmpty(); }
    %pythoncode {
    def __len__(self):
        return self.Size()

    def __iter__(self):
        it = $NCollection_ListIterator_Name(self)
        while it.More():
            yield it.Value()
            it.Next()
    }
};
"""
)

# the related pyi stub string
NCOLLECTION_LIST_EXTEND_TEMPLATE_PYI = Template(
    """
class $NCollection_List_Template_Instanciation:
    def __init__(self) -> None: ...
    def __len__(self) -> int: ...
    def Size(self) -> int: ...
    def Clear(self) -> None: ...
    def First(self) -> $Type_T: ...
    def Last(self) -> $Type_T: ...
    def Append(self, theItem: $Type_T) -> $Type_T: ...
    def Prepend(self, theItem: $Type_T) -> $Type_T: ...
    def RemoveFirst(self) -> None: ...
    def Reverse(self) -> None: ...
    def Value(self, theIndex: int) -> $Type_T: ...
    def SetValue(self, theIndex: int, theValue: $Type_T) -> None: ...
"""
)

# NCollection_Sequence and NCollection_List shares the
# same pyi and extension templates. It's just a copy/paste
# from the previous templates, it may change in the future
NCOLLECTION_SEQUENCE_EXTEND_TEMPLATE = Template(
    """
%extend $NCollection_Sequence_Template_Instanciation {
    // occt-800: NCollection_BaseSequence methods are not wrapped through
    // SWIG (its inner SeqNode has private new/delete). Re-export them per
    // instantiation so Python code can call .Size(), .Length(), .IsEmpty()
    // and use len() on every NCollection_Sequence<...>.
    size_t Size() const noexcept { return $$self->Size(); }
    int Length() const noexcept { return $$self->Length(); }
    bool IsEmpty() const noexcept { return $$self->IsEmpty(); }
    %pythoncode {
    def __len__(self):
        return self.Size()
    }
};
"""
)

# the related pyi stub string
NCOLLECTION_SEQUENCE_EXTEND_TEMPLATE_PYI = Template(
    """
class $NCollection_Sequence_Template_Instanciation:
    def __init__(self) -> None: ...
    def __len__(self) -> int: ...
    def Size(self) -> int: ...
    def Clear(self) -> None: ...
    def First(self) -> $Type_T: ...
    def Last(self) -> $Type_T: ...
    def Length(self) -> int: ...
    def Append(self, theItem: $Type_T) -> $Type_T: ...
    def Prepend(self, theItem: $Type_T) -> $Type_T: ...
    def RemoveFirst(self) -> None: ...
    def Reverse(self) -> None: ...
    def Value(self, theIndex: int) -> $Type_T: ...
    def SetValue(self, theIndex: int, theValue: $Type_T) -> None: ...
"""
)

SHAPE_ANALYSIS_FREE_BOUNDS_TEMPLATE = """
%extend ShapeAnalysis_FreeBounds {
    static Handle(TopTools_HSequenceOfShape) ConnectEdgesToWires(opencascade::handle<TopTools_HSequenceOfShape> & edges,
              const Standard_Real toler,
              const Standard_Boolean shared)
        {
            Handle(TopTools_HSequenceOfShape) owires = new TopTools_HSequenceOfShape;
            ShapeAnalysis_FreeBounds::ConnectEdgesToWires(edges, toler, shared, owires);
            return owires;
        }
    };

%extend ShapeAnalysis_FreeBounds {
    static Handle(TopTools_HSequenceOfShape) ConnectWiresToWires(opencascade::handle<TopTools_HSequenceOfShape> & iwires,
              const Standard_Real toler,
              const Standard_Boolean shared)
        {
            Handle(TopTools_HSequenceOfShape) owires = new TopTools_HSequenceOfShape;
            ShapeAnalysis_FreeBounds::ConnectWiresToWires(iwires, toler, shared, owires);
            return owires;
        }
    };
"""

SHAPE_ANALYSIS_FREE_BOUNDS_TEMPLATE_PYI = """    @staticmethod
    def ConnectEdgesToWires(edges: TopTools_HSequenceOfShape, toler: float, shared: bool) -> TopTools_HSequenceOfShape: ...
    @staticmethod
    def ConnectWiresToWires(iwires: TopTools_HSequenceOfShape, toler: float, shared: bool) ->  TopTools_HSequenceOfShape: ...
"""


# We extend the NCollection_DataMap template with a Keys
# method that returns a list of Keys
# TODO: do the same for other Key types
NCOLLECTION_DATAMAP_EXTEND_TEMPLATE = Template(
    """
%extend $NCollection_DataMap_Template_Instanciation {
    PyObject* Keys() {
        PyObject *l=PyList_New(0);
        for ($NCollection_DataMap_Template_Name::Iterator anIt1(*self); anIt1.More(); anIt1.Next()) {
          PyObject *o = PyLong_FromLong(anIt1.Key());
          PyList_Append(l, o);
          Py_DECREF(o);
        }
    return l;
    }
};
"""
)

TEMPLATE__EQ__ = Template(
    """
%extend{
    bool __eq_wrapper__($TYPE other) {
        if (*self==other) return true;
        else return false;
    }
}
%pythoncode {
def __eq__(self, right):
    try:
        return self.__eq_wrapper__(right)
    except:
        return False
}
"""
)

TEMPLATE__IMUL__ = Template(
    """
%extend{
    void __imul_wrapper__($TYPE other) {
    *self *= other;
    }
}
%pythoncode {
def __imul__(self, right):
    self.__imul_wrapper__(right)
    return self
}
"""
)

TEMPLATE__NE__ = Template(
    """
%extend{
    bool __ne_wrapper__($TYPE other) {
        if (*self!=other) return true;
        else return false;
    }
}
%pythoncode {
def __ne__(self, right):
    try:
        return self.__ne_wrapper__(right)
    except:
        return True
}
"""
)

TEMPLATE__IADD__ = Template(
    """
%extend{
    void __iadd_wrapper__($TYPE other) {
    *self += other;
    }
}
%pythoncode {
def __iadd__(self, right):
    self.__iadd_wrapper__(right)
    return self
}
"""
)

TEMPLATE__ISUB__ = Template(
    """
%extend{
    void __isub_wrapper__($TYPE other) {
    *self -= other;
    }
}
%pythoncode {
def __isub__(self, right):
    self.__isub_wrapper__(right)
    return self
}
"""
)

TEMPLATE__ITRUEDIV__ = Template(
    """
%extend{
    void __itruediv_wrapper__($TYPE other) {
    *self /= other;
    }
}
%pythoncode {
def __itruediv__(self, right):
    self.__itruediv_wrapper__(right)
    return self
}
"""
)

TEMPLATE_DUMPJSON = """
        /****************** DumpJson ******************/
        %feature("autodoc", "
Parameters
----------
depth: int, default=-1

Return
-------
str

Description
-----------
Dump the object to JSON string.
") DumpJson;
        %extend{
            std::string DumpJson(int depth=-1) {
            std::stringstream s;
            self->DumpJson(s, depth);
            return "{" + s.str() + "}" ;}
        };
"""

TEMPLATE_DUMPJSON_PYI = "    def DumpJson(self, depth: Optional[int]=-1) -> str: ...\n"

TEMPLATE_INITFROMJSON = """
        /****************** InitFromJson ******************/
        %feature("autodoc", "
Parameters
----------
json_string: the string

Return
-------
bool

Description
-----------
Init the object from a JSON string.
") InitFromJson;
        %extend{
            bool InitFromJson(std::string json_string) {
            std::stringstream s(json_string);
            Standard_Integer pos=2;
            return self->InitFromJson(s, pos);}
        };
"""

TEMPLATE_INITFROMJSON_PYI = (
    "    def InitFromJson(self, json_string: str) -> bool: ...\n"
)

TEMPLATE_GETTER_SETTER = Template(
    """
        %feature("autodoc","1");
        %extend {
            ${Return_Type} Get${Function_Name}(${Getter_Parameters_Types_Names}) {
            return (${Return_Type}) $$self->${Function_Name}(${Getter_Parameters_Names});
            }
        };
        %feature("autodoc","1");
        %extend {
            void Set${Function_Name}(${Setter_Parameters_Types_Names}) {
            $$self->${Function_Name}(${Getter_Parameters_Names})=value;
            }
        };
"""
)

TEMPLATE_GETTER_PYI = Template(
    "    def Get${Function_Name}(${Getter_Parameters_Hints}) -> ${Hint_Output_Type}: ...\n"
)

TEMPLATE_SETTER_PYI = Template(
    "    def Set${Function_Name}(${Setter_Parameters_Hints}) -> None: ...\n"
)

TIMESTAMP_TEMPLATE = Template(
    """
############################
Running pythonocc-generator.
############################
git revision : $GITREVISION

operating system : $OS

occt version targeted : $OCCTVERSION

date : $DATE
############################
"""
)

WIN_PRAGMAS = """
%{
#ifdef WNT
#pragma warning(disable : 4716)
#endif
%}

"""

GETSTATE_TEMPLATE = Template(
    """
%extend ${CLASSNAME} {
%pythoncode {
    def __getstate__(self):
        return self.DumpJson()
    }
};
"""
)


SETSTATE_TEMPLATE = Template(
    """
%extend ${CLASSNAME} {
%pythoncode {
    def __setstate__(self, state):
        inst = ${CLASSNAME}()
        if inst.InitFromJson(state):
            self.this = inst.this
        else:
            raise IOError('Failed to set state of ${CLASSNAME}')
    }
};
"""
)

TOPODS_CLASS = """
%pythoncode {
class topods:
    @staticmethod
    def Edge(*args, **kwargs):
        return Edge(*args, **kwargs)

    @staticmethod
    def Vertex(*args, **kwargs):
        return Vertex(*args, **kwargs)

    @staticmethod
    def Face(*args, **kwargs):
        return Face(*args, **kwargs)

    @staticmethod
    def Wire(*args, **kwargs):
        return Wire(*args, **kwargs)

    @staticmethod
    def Shell(*args, **kwargs):
        return Shell(*args, **kwargs)

    @staticmethod
    def Solid(*args, **kwargs):
        return Solid(*args, **kwargs)

    @staticmethod
    def CompSolid(*args, **kwargs):
        return CompSolid(*args, **kwargs)

    @staticmethod
    def Compound(*args, **kwargs):
        return Compound(*args, **kwargs)
};

"""

TOPODS_CLASS_PYI = """
class topods:
    @staticmethod
    def Edge(*args, **kwargs) -> TopoDS_Edge: ...
    @staticmethod
    def Vertex(*args, **kwargs) -> TopoDS_Vertex: ...
    @staticmethod
    def Face(*args, **kwargs) -> TopoDS_Face: ...
    @staticmethod
    def Wire(*args, **kwargs) -> TopoDS_Wire: ...
    @staticmethod
    def Shell(*args, **kwargs) -> TopoDS_Shell: ...
    @staticmethod
    def Solid(*args, **kwargs) -> TopoDS_Solid: ...
    @staticmethod
    def CompSolid(*args, **kwargs) -> TopoDS_CompSolid: ...
    @staticmethod
    def Compound(*args, **kwargs) -> TopoDS_Compound: ...

"""
TOPODS_SHAPE_PICKLE_TEMPLATE = """
%extend TopoDS_Shape {
%pythoncode {
    def __getstate__(self):
        from .BRepTools import breptools
        str_shape = breptools.WriteToString(self, True)
        return str_shape
    def __setstate__(self, state):
        from .BRepTools import breptools
        the_shape = breptools.ReadFromString(state)
        self.this = the_shape.this
    }
};
"""

HASH_TOPODS_SHAPE_TEMPLATE = """
%extend TopoDS_Shape {
    size_t __hash__() {
        std::hash<TopoDS_Shape> shapeHasher;
        size_t hashValue = shapeHasher(*self);
        return hashValue;
    }
};
"""

STANDARD_TRANSIENT_OPERATORS_TEMPLATE = """
%extend Standard_Transient {
    %pythoncode {
    __repr__ = _dumps_object

    def __eq__(self, right):
        if not isinstance(right, Standard_Transient):
            return False
        return self.__eq_wrapper__(right)

    def __ne__(self, right):
        if not isinstance(right, Standard_Transient):
            return True
        return self.__ne_wrapper__(right)
    }
};

%extend Standard_Transient {
    bool __eq_wrapper__(const opencascade::handle<Standard_Transient> & other) {
        if (self==other) return true;
        else return false;
    }
    bool __ne_wrapper__(const opencascade::handle<Standard_Transient> & other) {
        if (self!=other) return true;
        else return false;
    }
    size_t __hash__() {
        return opencascade::hash(self);
    }
};
"""

# for Geom, Geom2d, Poly, TColStd, TColgp, TShort
NUMPY_INIT_TEMPLATE = """
/*
numpy support for Geom, Geom2d, Poly, TColStd, TColgp, TShort see
https://github.com/tpaviot/pythonocc-core/pull/1381
*/
%{
#define SWIG_FILE_WITH_INIT
%}
%include ../common/numpy.i

%init %{
        import_array();
%}

%pythoncode {
    import numpy as np
}
%apply (double* IN_ARRAY1, int DIM1) { (double* numpyArrayU, int nRowsU) };
%apply (double* IN_ARRAY2, int DIM1, int DIM2) { (double* numpyArrayUV, int nRowsUV, int nColUV) };
%apply (double* ARGOUT_ARRAY1, int DIM1) { (double* numpyArrayResultArgout, int aSizeArgout) };

/*
end of numpy support section
*/
"""

BREPTOOLS_WRITE_READ_FROM_STRING = """
%feature("autodoc", "Serializes TopoDS_Shape to string. If full_precision is False, the default precision of std::stringstream is used which regularly causes rounding.") WriteToString;
%extend{
    static std::string WriteToString(const TopoDS_Shape & shape, bool full_precision = true) {
    std::stringstream s;
    if(full_precision) {
        s.precision(17);
        s.setf(std::ios::scientific);
    }
    BRepTools::Write(shape, s);
    return s.str();}
};
%feature("autodoc", "Deserializes TopoDS_Shape from string. Create and return a new TopoDS_Shape each time the method is called.") ReadFromString;
%extend{
    static TopoDS_Shape ReadFromString(const std::string & src) {
        std::istringstream s(std::move(src));
        TopoDS_Shape shape;
        BRep_Builder b;
        BRepTools::Read(shape, s, b);
        return shape;
    }
};
%feature("autodoc", "Deserializes TopoDS_Shape from string. Take a TopoDS_Shape instance by reference to prevent memory increase.") ReadFromString;
%extend{
    static void ReadFromString(const std::string & src, TopoDS_Shape& shape) {
        std::istringstream s(std::move(src));
        BRep_Builder b;
        BRepTools::Read(shape, s, b);
    }
};

"""

BREPTOOLS_WRITE_READ_FROM_STRING_PYI = """
    @staticmethod
    def WriteToString(sh: TopoDS_Shape) -> str: ...
    @staticmethod
    def ReadFromString(s: str) -> TopoDS_Shape: ...
    @staticmethod
    def ReadFromString(s: str, topods_shape: TopoDS_Shape) -> None: ...
"""

###########################
# Template for byref enum #
###########################
BYREF_ENUM_TEMPLATE = "ENUM_OUTPUT_TYPEMAPS(%s);\n"
