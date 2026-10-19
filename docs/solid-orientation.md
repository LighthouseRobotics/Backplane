# 3D coordinate orientation regression

Cameron Basham's PR [#57](https://github.com/i2cjak/Backplane/pull/57) rotates
standard glTF Y-up coordinates into the plot protocol's Z-up coordinates:
`(x, y, z) → (x, -z, y)`. This is a proper rotation with determinant +1, so
triangle winding and the normals computed from it retain their handedness.
The earlier axis swap had determinant -1. Bounds use the same transformed
coordinates as vertices.

The native renderer consumes Y-up triangles directly. STEP conversion starts
with Z-up millimetres; `Mech.metres` and `Mech.upright` normalize it before the
shared plot encoder. The encoder's rotation therefore restores the original
STEP axes and converts to the wire's 10 micrometre units.

Run from the repository root:

```sh
bend test/plot_test.bend
bend test/solid_orientation_test.bend
mkdir -p build/orientation
bend test/tools/solid_roundtrip.bend -o build/solid-roundtrip.mjs
node test/tools/solid_roundtrip.mjs build/solid-roundtrip.mjs build/orientation
PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core/index.mjs \
  CHROME=/absolute/path/to/chrome \
  node test/tools/solid_browser.mjs build/orientation
scripts/check.sh
```

The generated fixture is original synthetic geometry and needs no CAD library
or external file. Its GLB names three unequal, colored landmarks:
`FRONT_RED_F.Cu`, `BACK_BLUE_B.Cu` and `RIGHT_GREEN`. The first sits above the
board plane, the second below with a downward normal and signed coordinates,
and the third faces +X. Board/glTF input uses metres and Y up; the second
fixture emulates STEP converter output in millimetres and Z up.

The test exercises `Glb.parse`, `Mesh.tris`, the STEP normalization where
appropriate, `Solid.thin`, `Solid.of`, `Plot.msg.solid`, and the actual
`src/web/solid.js` CBOR/mesh decoder. It checks explicit expected coordinates,
signed bounds, unit conversion, labels, normals, winding and the inverse native
rotation. Production `Solid.thin` deliberately moves planar vertices to cell
centres at 1/1000 of the model diagonal. The fixture's expected planar tolerance
is calculated independently as half that cell plus half a wire rounding unit
(under 1.493 wire units, or 0.015 mm). Heights stay exact, and encoder bounds
must exactly equal the bounds of decoded vertices. This preserves coverage for
mirroring while accommodating the production simplifier. The browser check uses the production WebGL view and captures top,
bottom and oblique frames while checking colored landmarks and screen direction.
The fixtures are labeled geometry; they do not claim to be a KiCad export.

Run the same JS runner against a baseline module compiled from main at
`30884966ef59c383581bcd1b7653f8f739cf009e` using the identical Bend wrapper. It must
fail on a board-position assertion, providing a negative control for the
mirroring defect.

Web, iOS and Android share the encoded mesh. Their decoders recompute normals
from the same ordered vertices. Linux tests exercise the browser decoder and
rendering; they do not certify Swift/Metal, Kotlin/GLES, physical devices or a
native window. The generated `.cbor` fixtures can be reused in those acceptance
lanes without CAD dependencies.

On Linux Node 22.23.3 and Chrome 155.0.8059.84 with SwiftShader, both production
round trips passed and all six browser views passed their landmark assertions.
The screenshots were visually inspected. Both inputs produced signed bounds
`[-399,-300,-100,1100,899,400]` in wire units, including the documented planar
snapping. The identical baseline wrapper on main failed its first Y coordinate
(`-300` instead of `300`), the expected reflection negative control. The original
PR's exact unthinned-coordinate regression tests remain in place.

A separate Linux acceptance lane exported the pinned official ecc83 fixture
using the verified KiCad 10.99.0-bp.4 CLI, then decoded and rendered that real
export through the candidate production GLB parser/encoder and web renderer.
It produced 48,486 vertices, 488 pixel colors and the PCB/copper/pad/silkscreen
groups, with an inspected screenshot. The Node GLB wrapper overflowed its
default stack in `Bytes.take`; a 192 MiB test stack completed. This is evidence
for that export and web view, and does not establish native rendering, phone
stack limits or physical-device acceptance.
