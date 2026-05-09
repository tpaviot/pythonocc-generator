# OCCT C++ ↔ pythonocc Python: API Contract

This document describes precisely what the generator does to translate an OCCT
C++ declaration into the Python API exposed by
[pythonocc-core](https://github.com/tpaviot/pythonocc-core). It is the
reference for what a wrapped class or method *will look like* before you write
the Python call.

The translation is intentionally **literal**: identifiers, ownership and call
shapes follow OCCT, not Python conventions. The goal is to make porting C++
OCCT code to Python mechanical and to let the official OCCT documentation
remain useful.

Source of truth for every rule below: [`src/generate_wrapper.py`](src/generate_wrapper.py).

---

## 1. Modules, classes, methods

| OCCT C++ | pythonocc Python |
|---|---|
| Module `gp` (collection of `gp_*.hxx` headers) | `OCC.Core.gp` |
| Class `gp_Pnt` | `OCC.Core.gp.gp_Pnt` |
| Method `gp_Pnt::Distance(const gp_Pnt&)` | `OCC.Core.gp.gp_Pnt.Distance(other)` |
| Static method `BRepTools::Read` | `BRepTools.Read(...)` (call on the class, not an instance) |
| Free function `Foo::SomeFreeFunc` (in module `Foo`) | `OCC.Core.Foo.SomeFreeFunc(...)` |
| Free function from another namespace | **skipped** |
| Class name == module name (e.g. `TopoDS`) | renamed lowercase: `OCC.Core.TopoDS.topods` |

There is **no** PEP 8 conversion. `gp_Pnt`, `BRepPrimAPI_MakeBox`,
`MakeFromCurve` etc. keep their OCCT spelling.

```cpp
// C++
gp_Pnt p(0., 0., 0.);
double d = p.Distance(other);
```
```python
# Python
from OCC.Core.gp import gp_Pnt
p = gp_Pnt(0.0, 0.0, 0.0)
d = p.Distance(other)
```

### Module ↔ class collision

OCCT exposes `TopoDS::Edge`, `TopoDS::Wire`, … as namespace functions next to
the `TopoDS_Edge`, `TopoDS_Wire` classes. The generator emits a Python class
**`topods`** in `OCC.Core.TopoDS` that exposes these as `@staticmethod`s, plus
the lowercase rename for any C++ class whose name matches its module. So:

```python
from OCC.Core.TopoDS import topods, TopoDS_Edge
edge = topods.Edge(some_shape)        # OCCT TopoDS::Edge(...)
isinstance(edge, TopoDS_Edge)         # True
```

---

## 2. Handles (`Standard_Transient` hierarchy)

Any OCCT class that inherits from `Standard_Transient` is reference-counted in
C++ via `Handle(Foo)` (alias `Handle_Foo`, alias since OCCT 8.0
`occ::handle<Foo>`, internally `opencascade::handle<Foo>`).

The generator detects this hierarchy from `DEFINE_STANDARD_HANDLE`,
`DEFINE_STANDARD_RTTI*`, and `DEFINE_DERIVED_ATTRIBUTE` macros, then emits
`%wrap_handle` + `%make_alias` so:

- Python users **never see** the handle. They manipulate the underlying class
  directly. SWIG converts both ways at the boundary.
- The Python class transparently accepts and returns instances where the C++
  signature uses `Handle(Foo)` / `opencascade::handle<Foo>`.

```cpp
// C++ — three equivalent declarations as far as Python is concerned
void DoSomething(const Handle(Geom_Curve)& c);
void DoSomething(const opencascade::handle<Geom_Curve>& c);
void DoSomething(const occ::handle<Geom_Curve>& c);
```
```python
# Python — the call shape is always the same
DoSomething(curve)         # `curve` is a Geom_Curve (or any subtype)
```

### Standard_Transient itself

`Standard_Transient` gets three Python operators by reference identity:

```python
a == b   # True iff a and b wrap the same C++ object
a != b
hash(a)  # opencascade::hash(self)
```

`__repr__` falls back to `_dumps_object` from pythonocc-core.

---

## 3. Operators

| C++ operator | Python translation |
|---|---|
| `operator+`, `operator-`, `operator*`, `operator/` | wrapped natively by SWIG (`a + b`, …) |
| `operator==` | `__eq__` (returns `False` on type mismatch instead of raising) |
| `operator!=` | `__ne__` |
| `operator+=` | `__iadd__` |
| `operator-=` | `__isub__` |
| `operator*=` | `__imul__` |
| `operator/=` | `__itruediv__` |
| any other operator | **skipped** (with a log entry) |

The `==`/`!=` wrappers swallow type errors silently so a comparison against a
foreign type returns `False`/`True` rather than raising.

---

## 4. Out parameters → tuple returns

OCCT methods that return values through non-`const` reference parameters are
turned into Python methods that return a tuple (`return_value, *out_values`).

| C++ parameter type | Python effect |
|---|---|
| `Standard_Real&` (or `double&`) | added to the return tuple as `float` |
| `Standard_Integer&` (or `int&`) | added as `int` |
| `Standard_ShortReal&` (or `float&`) | added as `float` |
| `Standard_Boolean&` (or `bool&`) | added as `bool` |
| `Standard_OStream&` / `std::ostream&` | added as `str` |
| `opencascade::handle<TCollection_HAsciiString>&` | added as `TCollection_HAsciiString` |
| any enum passed by reference | added as that enum |

A parameter named `Standard_Real & val` becomes `Standard_Real &OutValue`
under the hood, which SWIG maps to a Python output.

```cpp
// C++
gp_Pnt2d p;
Standard_Boolean SomeMethod(Standard_Real& u, Standard_Real& v) const;
```
```python
# Python
ok, u, v = p.SomeMethod()
```

If the function returns `void` and has at least one out-parameter, the return
type collapses to either the single out value or a tuple of all of them.

---

## 5. Getter / setter synthesis for primitive references

Some OCCT classes expose a single mutable accessor `T& Foo()` instead of a
`Foo` / `SetFoo` pair. Python cannot assign through a reference returned from
a function call, so the generator synthesizes the missing setter.

### Method with parameters returning a primitive ref

```cpp
// C++
Standard_Real& Value(const Standard_Integer i) const;
```
becomes two methods:
```python
GetValue(i: int) -> float
SetValue(i: int, value: float) -> None
```

### Method with no parameters returning a primitive ref

For any parameterless method `T& Foo()` (with `T` ∈ `Standard_Real`,
`Standard_Integer`, `Standard_Boolean`, or their plain-C aliases), the
generator emits:
```python
GetFoo() -> T
SetFoo(value: T) -> None
```

This restores the API pythonocc has exposed since 2014.

---

## 6. Enums

Each enum is emitted twice:

1. As a SWIG enum (so C++ signatures using it stay typed).
2. As a Python proxy class derived from `IntEnum`, plus module-level aliases
   for every enumerator.

```cpp
// C++
enum TopAbs_Orientation {
  TopAbs_FORWARD,
  TopAbs_REVERSED,
  TopAbs_INTERNAL,
  TopAbs_EXTERNAL
};
```
```python
# Python
class TopAbs_Orientation(IntEnum):
    TopAbs_FORWARD: int = 0
    TopAbs_REVERSED: int = 1
    TopAbs_INTERNAL: int = 2
    TopAbs_EXTERNAL: int = 3

TopAbs_FORWARD = TopAbs_Orientation.TopAbs_FORWARD   # alias at module level
```

Notes:

- `enum class X` (scoped enums) are preserved as scoped enums.
- An enum value whose name collides with a Python keyword is suffixed with `_`
  (e.g. `None` → `None_`).
- An enum passed *by reference* (e.g. `TopAbs_Orientation& Or`) is registered
  in `EnumTemplates.i` via `ENUM_OUTPUT_TYPEMAPS(...)` so it can be returned
  through the tuple-return mechanism.
- `enum` values like `(unsigned int)(1 << int(X))` are simplified to `X`
  (otherwise SWIG cannot parse them).

---

## 7. Typedefs and templates

### Plain class aliases

A `typedef Foo Bar;` whose RHS is a wrapped class becomes a Python alias:

```python
# In OCC.Core.<module>.py
Bar = Foo
```
and a `NewType("Bar", Foo)` in the `.pyi` so static type checkers
understand both names.

A `using Bar = Foo;` (C++11 alias declaration) is rewritten to the classic
`typedef Foo Bar;` form before parsing — *unless* `Foo` is a template (RHS
contains `<`), in which case it is left alone (the generator does not
instantiate it).

### NCollection templates

Each `typedef NCollection_X<...> Y;` becomes a `%template(Y) NCollection_X<...>;`
SWIG instantiation, plus container-specific extensions:

| C++ template | Python additions |
|---|---|
| `NCollection_Array1<T>` | numpy interop for primitive `T`; iteration; `__len__`; `__getitem__`/`__setitem__` |
| `NCollection_Array2<T>` | numpy interop for primitive `T` |
| `NCollection_List<T>` | `__iter__` (forwards to `<typedef>Iterator`); `__len__`; `Size`/`Length`/`IsEmpty` re-exported |
| `NCollection_Sequence<T>` | `__len__`; `Size`/`Length`/`IsEmpty` re-exported |
| `NCollection_DataMap<K,V>` | `Keys()` returns a Python list (only when `K` is `Standard_Integer`/`int`) |
| `NCollection_IndexedMap<T>`, `NCollection_IndexedDataMap<...>` | `Items`/`KeyValues`/`IndexedItems`/`Contained` are `%ignore`d (non-default-constructible views) |
| `NCollection_HArray1<T>` / `HArray2<T>` / `HSequence<T>` | wrapped as transient handles via `%make_alias` (see §8) |

### `Handle_T &` parameters

Any function whose parameters contain `Handle_T &` is silently skipped — it
maps to a template parameter SWIG cannot disambiguate.

---

## 8. HArray1 / HArray2 / HSequence

OCCT 8.0 dropped the `DEFINE_HARRAY1` / `DEFINE_HARRAY2` / `DEFINE_HSEQUENCE`
macros; the generator now also picks up the equivalent
`typedef NCollection_HArray1<T> Foo;` form via a pre-pass
(`scan_typedef_aliases`) over a curated subset of headers.

For each detected typedef the generator emits:

- a fake transient class (`HARRAY1_TEMPLATE` / `HARRAY2_TEMPLATE` /
  `HSEQUENCE_TEMPLATE`) inheriting from the array/sequence base + `Standard_Transient`,
- the matching `%make_alias` so the handle works,
- a `.pyi` stub class.

This is necessary because the OCCT 8.0 templates are otherwise opaque to SWIG.

---

## 9. NumPy interop

NumPy is initialized only for these modules: `Geom`, `Geom2d`, `Poly`,
`TColStd`, `TColgp`, `TShort`. For these, the generated `.i` file imports
`numpy.i` and exposes:

- `Array1NumpyTemplate` for `NCollection_Array1<{double, float, int}>` and
  `NCollection_Array1<Poly_Triangle>`,
- `Array1Of2DNumpyTemplate` for `Array1<gp_XY>`, `Array1<gp_Vec2d>`,
  `Array1<gp_Pnt2d>`, `Array1<gp_Dir2d>`,
- `Array1Of3DNumpyTemplate` for `Array1<gp_XYZ>`, `Array1<gp_Vec>`,
  `Array1<gp_Pnt>`, `Array1<gp_Dir>`,
- `Array2NumpyTemplate` for the 2D equivalents.

In addition, `Geom_Curve`, `Geom_Surface`, and `Geom2d_Curve` are extended
with numpy-typed evaluation helpers (`CurveArrayEvalExtend`,
`CurveArrayEvalExtend2d`, `SurfaceArrayEvalExtend`).

```python
import numpy as np
from OCC.Core.TColgp import TColgp_Array1OfPnt
arr = TColgp_Array1OfPnt(1, 10)
xyz = np.asarray(arr)        # zero-copy view, when the numpy path applies
```

---

## 10. Strings and streams

| C++ type | Python type |
|---|---|
| `Standard_CString` (`const char*`) | `str` |
| `TCollection_AsciiString` | `str` (transparent at the boundary) |
| `TCollection_ExtendedString` | `str` |
| `Standard_IStream` | `std::istream` (rare; SWIG typemap) |
| `Standard_SStream` / `std::stringstream` | `std::stringstream` |

For the docstring generator, `TCollection_AsciiString` and
`TCollection_ExtendedString` parameter types are documented as plain `str`.

---

## 11. Pickling and JSON serialization

### `DumpJson` / `InitFromJson`

Any class that exposes `DumpJson` and/or `InitFromJson` gets a Python wrapper
that reshapes the C++ stream-based API into a string-based one:

```python
text = obj.DumpJson(depth=-1)
obj.InitFromJson(text)        # returns bool
```

If a class exposes **both** `DumpJson` and `InitFromJson` (and is not
`TopoDS_Shape`), the generator additionally emits `__getstate__` /
`__setstate__` so the object pickles via JSON round-trip.

### `TopoDS_Shape`

`TopoDS_Shape` is special-cased:

- pickling goes through `BRepTools::WriteToString` / `ReadFromString`
  (full-precision serialization of the BREP),
- `__hash__` is `std::hash<TopoDS_Shape>{}(self)`,
- `BRepTools` itself is extended with the static helpers
  `WriteToString(shape, full_precision=True) -> str`,
  `ReadFromString(text) -> TopoDS_Shape`,
  `ReadFromString(text, out_shape) -> None`.

---

## 12. Class-specific extensions

A handful of classes get hand-written shims (in `_class_specific_extensions`):

| Class | Added |
|---|---|
| `BRepTools` / `BRepTools_ShapeSet` | `WriteToString`, `ReadFromString` |
| `TDF_Label` | `GetLabelName() -> str` (reads the optional `TDataStd_Name` attribute) |
| `StlAPI_Writer` | `SetASCIIMode(mode: bool)` (OCCT 8.0 dropped the original setter) |
| `math_Matrix` | `GetValue(row, col)` / `SetValue(row, col, value)` |
| `math_Vector` | `GetValue(idx)` / `SetValue(idx, value)` |
| `Geom_Curve`, `Geom2d_Curve`, `Geom_Surface` | numpy evaluation extensions |
| `ShapeAnalysis_FreeBounds` | `ConnectEdgesToWires`, `ConnectWiresToWires` returning the result instead of taking it as out-arg |

---

## 13. Module-specific SWIG block injections

Some modules need a custom block of SWIG directives prepended to the body:

| Module | Inserted block |
|---|---|
| `NCollection` | base `NCollection_*` templates and minimal shims for `NCollection_PackedMap`, `NCollection_DynamicArray`, `NCollection_HArray1/2`, `NCollection_HSequence` |
| `math` | `%template(math_Vector) math_VectorBase<double>` |
| `BVH` | `%include "BVH_PrimitiveSet.hxx"` |
| `Prs3d` | `%include "Prs3d_Point.hxx"` |
| `Graphic3d` | `Handle_Graphic3d_TextureSet` and friends as `%define`s |
| `BRepAlgoAPI` | `%include "BRepAlgoAPI_Algo.hxx"` |

---

## 14. Method-level skips (silent)

A method is skipped (`return "", ""`) when:

- it is a destructor (`~Foo()`) or `f["returns"] == "~"`;
- the return type contains `TYPENAME` (something in NCollection);
- the function name is `DEFINE_STANDARD_RTTIEXT` or `Handle`;
- it is templated (`f["template"]` is truthy);
- it is a free function whose namespace is not the current module;
- it is an operator that is neither in the supported list nor handled
  natively by SWIG;
- one of its parameters has `Handle_T &` in its type.

These do not add to the wrapped-method counter.

---

## 15. Excluded classes and methods (`@classnotwrapped` / `@methodnotwrapped`)

Entries listed in `modules.yaml` under `exclude_classes` or
`exclude_member_functions` get a Python placeholder that **raises** at use
time, rather than disappearing silently:

```python
# Excluded class
@classnotwrapped
class Foo_BadClass:
    pass

# Excluded method on a wrapped class
class Foo_GoodClass:
    @methodnotwrapped
    def BadMethod(self):
        pass
```

Classes that NCollection.i wraps directly (`NCollection_Array1`,
`NCollection_Map`, …) are deliberately *not* shadowed by a placeholder, even
when listed for exclusion, since the placeholder would hide the real wrapped
class.

The corresponding `.pyi` stubs use `class Foo_BadClass: ...` so static type
checkers still know about them.

---

## 16. Source-level rewrites applied to OCCT headers

Before CppHeaderParser parses a header, `adapt_header_file` mutates the source
to remove or rewrite constructs the parser cannot handle:

| Found in source | Action |
|---|---|
| `DEFINE_STANDARD_HANDLE(C, P)` | record `C`, then `//` the macro |
| `DEFINE_STANDARD_RTTI{,_INLINE,EXT}(C, P)`, `DEFINE_DERIVED_ATTRIBUTE(C, P)` | record `C` as a handle, then `//` the macro |
| `DEFINE_HARRAY1(C, B)`, `DEFINE_HARRAY2`, `DEFINE_HSEQUENCE` | register the class for §8 wrapping |
| `Standard_DEPRECATED("...")` (with parens) | removed entirely |
| bare `Standard_DEPRECATED` | `//`-commented |
| `DECLARE_TOBJOCAF_PERSISTENCE` | `//`-commented |
| `DEFINE_DERIVED_ATTRIBUTE` (occurrence outside macro) | `//`-commented |
| `DEFINE_STANDARD_ALLOC`, `Standard_EXPORT`, `Standard_NODISCARD` | stripped |
| `occ::handle` (OCCT 8.0 short alias) | rewritten to `opencascade::handle` |
| `using X = Y;` (Y is not a template) | rewritten to `typedef Y X;` |
| `Handle(Foo)` | rewritten to `opencascade::handle<Foo>` |
| Headers containing `"Deprecated alias to moved class"` or `"Alias to moved class"` | parsed as empty (skipped entirely) |

---

## 17. Globally excluded entities

`src/_exclusions.py` holds the exclusion lists that are not module-scoped:

- `HXX_TO_EXCLUDE_FROM_CPPPARSER` — headers the parser chokes on (e.g.
  `NCollection_ForwardRange.hxx` due to C++17 SFINAE).
- `HXX_TO_EXCLUDE_FROM_BEING_INCLUDED` — headers that fail to compile
  (e.g. WNT-only headers).
- `TYPEDEF_TO_EXCLUDE` — typedefs that produce SWIG syntax errors or shadow
  other typedefs.
- `STANDARD_INTEGER_TYPEDEF` — typedefs that should be flattened to plain `int`
  in parameter and return types.
- `ENUMS_TO_EXLUDE` — enums to skip entirely (`ShapeMapGroup`, `AllocatorType`).
- `NODEFAULTCTOR` — classes that must not get a `%nodefaultctor` directive.
- `TEMPLATES_TO_EXCLUDE` — template typedefs that cannot be instantiated.
- `NCOLLECTION_WRAPPED_CLASSES` — classes that NCollection.i already wraps and
  must therefore not get a `@classnotwrapped` shadow.

Entries are platform-aware: any header whose path contains `WNT`, `wnt`, `X11`,
`XWD`, or `Cocoa` is filtered out so generation is OS-independent.

---

## 18. Dependency tracking

For each parameter and return type encountered, `check_dependency()`
identifies the OCCT module the type belongs to (e.g. `TopoDS_Shape` →
`TopoDS`) and registers it in `state.python_module_dependency`. This list
drives:

- the `#include <Dep_module.hxx>` lines emitted in the `%{...%}` block,
- the `%import Dep.i` lines that let SWIG see the cross-module type tags,
- the `from OCC.Core.Dep import *` lines in the `.pyi` stub.

All wrapping passes (typedef adaptation, return type, parameter list,
docstring) call `check_dependency` as a side-effect; the *order* in which
they run defines the order of these `#include`/`%import` lines. The
generator preserves a specific order (parameters before return type) so the
generated output is reproducible.

---

## 19. Limitations

- C++ class templates without an explicit instantiation are skipped (SWIG
  cannot wrap them).
- Functions whose signatures contain unresolved `Handle_T &` are skipped.
- Operators outside the supported set (§3) are skipped silently.
- Free functions defined outside the current module's namespace are skipped.
- Some headers cannot be parsed at all and are listed in
  `HXX_TO_EXCLUDE_FROM_CPPPARSER`. Their classes are unreachable from Python.

---

## 20. Where to look in the source

- `process_function` (`src/generate_wrapper.py`) — per-function pipeline.
- `process_classes` — per-class pipeline.
- `process_typedefs` / `process_templates_from_typedefs` — typedef pipeline.
- `process_enums` — enum pipeline.
- `adapt_header_file` — pre-parsing source rewrites (§16).
- `_class_specific_extensions` — hand-written shims (§12).
- `_exclusions.py` — global exclusion lists (§17).
- `_swig_templates.py` — every `.i` / `.pyi` template fragment.
- `modules.yaml` — per-module configuration (deps + exclusions).
