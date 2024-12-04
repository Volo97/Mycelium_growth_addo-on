bl_info = {
    "name": "Mycelium Growth",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "category": "Add Mesh",
}

import bpy
import bmesh
from mathutils import Vector, Matrix, kdtree
from mathutils.bvhtree import BVHTree
import random
import math
from bpy.props import FloatProperty, IntProperty, FloatVectorProperty, BoolProperty

class MyceliumGrowthOperator(bpy.types.Operator):
    bl_idname = "object.grow_mycelium"
    bl_label = "Grow Mycelium"
    bl_options = {'REGISTER', 'UNDO'}
    
    def organic_direction(self, direction, normal, strength=0.3):
        noise = Vector((
            random.uniform(-1, 1),
            random.uniform(-1, 1),
            random.uniform(-1, 1)
        ))
        
        blend_dir = direction.lerp(normal, random.uniform(0, strength))
        result = blend_dir.lerp(noise, 0.3)
        return result.normalized()

    def execute(self, context):
        props = context.scene.mycelium_props
        target = context.active_object
        
        depsgraph = context.evaluated_depsgraph_get()
        target_eval = target.evaluated_get(depsgraph)
        mesh = target_eval.data
        bm_target = bmesh.new()
        bm_target.from_mesh(mesh)
        bmesh.ops.triangulate(bm_target, faces=bm_target.faces)
        
        bm_target.faces.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bm_target)
        
        mycelium_mesh = bpy.data.meshes.new("Mycelium")
        mycelium = bpy.data.objects.new("Mycelium", mycelium_mesh)
        context.scene.collection.objects.link(mycelium)
        
        bm = bmesh.new()
        for _ in range(props.start_points):
            face = random.choice(bm_target.faces)
            
            coords = [v.co for v in face.verts]
            weights = [random.random() for _ in range(len(coords))]
            total = sum(weights)
            weights = [w/total for w in weights]
            
            pos = Vector((0, 0, 0))
            for coord, weight in zip(coords, weights):
                pos += coord * weight
            
            v1 = bm.verts.new(pos)
            v2 = bm.verts.new(pos + face.normal * 0.01)
            bm.edges.new((v1, v2))
        
        bm.to_mesh(mycelium_mesh)
        bm.free()
        
        for iteration in range(props.iterations):
            mesh = mycelium.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            
            tips = [v for v in bm.verts if len(v.link_edges) == 1]
            
            for tip in tips:
                edge = tip.link_edges[0]
                other = edge.other_vert(tip)
                base_direction = (tip.co - other.co).normalized()
                
                location, normal, _, _ = bvh.find_nearest(tip.co)
                if not location:
                    continue
                
                for _ in range(props.branches):
                    if random.random() > props.branching_prob:
                        continue
                    
                    growth_dir = self.organic_direction(base_direction, normal, props.attraction_strength)
                    
                    curve_factor = (iteration + 1) / props.iterations
                    growth_dir = growth_dir.lerp(normal, curve_factor * 0.3)
                    
                    length = random.uniform(props.min_length, props.max_length) * (1 - curve_factor * 0.5)
                    new_pos = tip.co + growth_dir * length
                    
                    location, normal, _, _ = bvh.find_nearest(new_pos)
                    if location:
                        offset = normal * random.uniform(0.001, 0.01)
                        new_vert = bm.verts.new(location + offset)
                        bm.edges.new((tip, new_vert))
            
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()
        
        bm_target.free()
        
        mycelium.select_set(True)
        context.view_layer.objects.active = mycelium
        bpy.ops.object.convert(target='CURVE')
        mycelium.data.bevel_depth = props.thickness
        mycelium.data.resolution_u = 16
        mycelium.data.bevel_resolution = 4
        mycelium.data.use_fill_caps = True
        mycelium.data.fill_mode = 'FULL'
        bpy.ops.object.shade_smooth()
        
        mat = bpy.data.materials.new(name="MyceliumMat")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = props.color
        mycelium.data.materials.append(mat)
        
        return {'FINISHED'}

class MyceliumProperties(bpy.types.PropertyGroup):
    iterations: IntProperty(
        name="Iterations",
        description="Number of growth iterations",
        default=9,
        min=1
    )
    start_points: IntProperty(
        name="Starting Points",
        description="Number of initial growth points",
        default=1,
        min=1
    )
    branches: IntProperty(
        name="Branches",
        description="Number of branches per growth point",
        default=3,
        min=1
    )
    branching_prob: FloatProperty(
        name="Branching Probability",
        description="Probability of creating a branch",
        default=1.00,
        min=0.0,
        max=1.0
    )
    max_angle: FloatProperty(
        name="Max Angle",
        description="Maximum branching angle in radians",
        default=1.30,
        min=0.0,
        max=math.pi
    )
    min_length: FloatProperty(
        name="Min Length",
        description="Minimum branch length",
        default=0.06,
        min=0.01
    )
    max_length: FloatProperty(
        name="Max Length",
        description="Maximum branch length",
        default=0.13,
        min=0.01
    )
    max_distance: FloatProperty(
        name="Max Distance",
        description="Maximum distance to target mesh",
        default=3.10,
        min=0.01
    )
    attraction_strength: FloatProperty(
        name="Attraction Strength",
        description="Strength of attraction to target mesh",
        default=0.30,
        min=0.0,
        max=1.0
    )
    thickness: FloatProperty(
        name="Thickness",
        description="Mycelium thickness",
        default=0.00,
        min=0.001
    )
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0, 1.0),
        size=4,
        min=0.0,
        max=1.0
    )

class OBJECT_PT_mycelium(bpy.types.Panel):
    bl_label = "Mycelium Growth"
    bl_idname = "OBJECT_PT_mycelium"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        props = context.scene.mycelium_props

        layout.operator("object.grow_mycelium")
        
        box = layout.box()
        box.label(text="Growth Parameters:")
        box.prop(props, "iterations")
        box.prop(props, "start_points")
        box.prop(props, "branches")
        box.prop(props, "branching_prob")
        box.prop(props, "max_angle")
        box.prop(props, "min_length")
        box.prop(props, "max_length")
        box.prop(props, "max_distance")
        box.prop(props, "attraction_strength")
        
        box = layout.box()
        box.label(text="Appearance:")
        box.prop(props, "thickness")
        box.prop(props, "color")

classes = (
    MyceliumGrowthOperator,
    MyceliumProperties,
    OBJECT_PT_mycelium
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mycelium_props = bpy.props.PointerProperty(type=MyceliumProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.mycelium_props

if __name__ == "__main__":
    register()
    
    if bpy.context.active_object:
        bpy.ops.object.grow_mycelium()
    else:
        print("Select a target mesh first!")
