local exports = exports or {}
local LeftIn = LeftIn or {}
LeftIn.__index = LeftIn
function LeftIn.new(construct, ...)
    local self = setmetatable({}, LeftIn)
    self.text = nil
    self.tween = nil
    self.tween1 = nil
    self.comp = nil
    if construct and LeftIn.constructor then LeftIn.constructor(self, ...) end
    return self
end

function LeftIn:constructor()

end

local function updateHandle(comp)
    if comp == nil then 
        return 
    end

    local animTrans = comp.entity:getComponent("Transform")
    local parentTrans = animTrans.parent
    
    local userS = parentTrans.localScale
    local userR = parentTrans.localOrientation
    local userT = parentTrans.localPosition

    local animS = animTrans.localScale
    local animR = animTrans.localOrientation
    local animT = animTrans.localPosition

    local mat = parentTrans.localMatrix
    
    -- move to (0,0)
    mat:AddTranslate(animT * userS.x)

    -- set anim local matrix
    local animLocal = parentTrans.localMatrix:Invert_Full() * mat
    animTrans.localMatrix = animLocal
end

function LeftIn:onStart(comp)
    self.comp = comp
    local screenW = Amaz.BuiltinObject:getOutputTextureWidth()
    local transform = comp.entity:getComponent("Transform")
    local textureW = 0.3*screenW
    -- local sprite = comp.entity:getComponent("Sprite2DRenderer")
    -- self.text = comp.entity:getComponent("SDFText")
    
    -- if sprite ~= nil then
    --     local material = sprite.material
    --     textureW = sprite:getTextureSize().x
    --     self.tween = comp.entity.scene.tween:fromTo(material, {["_alpha"] = 0.0}, {["_alpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    -- end

    -- if self.text ~= nil then
    --     textureW = self.text.rect.width
    --     self.tween = comp.entity.scene.tween:fromTo(self.text, {["alpha"] = 0.0}, {["alpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    -- end
    self.shape = comp.entity:getComponent("IFShape")
    -- self.shapeElements = self.shape.shapeElements
    -- self.shapeGroup = self.shapeElements:get(0)
    if self.shape ~= nil then
        self.tween = comp.entity.scene.tween:fromTo(self.shape, {["shapeGlobalAlpha"] = 0.0}, {["shapeGlobalAlpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    end

    self.tween1 = comp.entity.scene.tween:fromTo(transform, {["localPosition"] = Amaz.Vector3f(-2.66 * textureW / screenW, 0.0, 0.0) }, {["localPosition"] = Amaz.Vector3f(0.0, 0.0, 0.0) }, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
end

function LeftIn:seek(time)
    self.tween:set(time)
    self.tween1:set(time)
    updateHandle(self.comp)
end

function LeftIn:setDuration(duration)
    self.tween.duration = duration
    self.tween1.duration = duration
end

function LeftIn:clear()
    if self.tween then
        self.tween:set(self.tween.duration)
        self.tween:clear()
        self.tween = nil
    end
    if self.tween1 then
        self.tween1:set(self.tween1.duration)
        self.tween1:clear()
        self.tween1 = nil
    end
end
exports.LeftIn = LeftIn
return exports
