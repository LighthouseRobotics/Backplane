import Base
import ../../src/core/glb.bend as G
import ../../src/core/plot.bend as P
import ../../src/core/mech.bend as M

# The pure production stages used by server/plot.bend, including STEP's
# millimetre conversion and upright rotation before the shared encoder.
def triangles(bs: List<&2, U32>, step: Bool) -> List<&2, G.Tri3>:
  match step:
    case True{}:
      M.Mech.upright(M.Mech.metres(G.Mesh.tris(G.Glb.parse(bs))))
    case False{}:
      G.Mesh.tris(G.Glb.parse(bs))

def packet(bs: List<&2, U32>, step: Bool) -> List<&2, U32>:
  P.Plot.msg.solid("2|fixture|orientation.glb", P.Solid.of(P.Solid.thin(triangles(bs, step))))

def parts(bs: List<&2, U32>) -> G.Mesh:
  G.Glb.parse(bs)
