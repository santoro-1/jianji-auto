local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
    local self = setmetatable({}, Transform)
    self.text = nil
    self.tween = nil
    self.tween1 = nil
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end

function Transform:onStart(comp)
    local sprite = comp.entity:getComponent("Sprite2DRenderer")
    self.text = comp.entity:getComponent("SDFText")

    if sprite ~= nil then
        local material = sprite.material
        self.tween = comp.entity.scene.tween:fromTo(material, {["_alpha"] = 1.0}, {["_alpha"] = 0.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    end

    if self.text ~= nil then
        self.tween = comp.entity.scene.tween:fromTo(self.text, {["alpha"] = 1.0}, {["alpha"] = 0.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    end

    local transform = comp.entity:getComponent("Transform")
    self.tween1 = comp.entity.scene.tween:fromTo(transform,
    {
        ["localScale"] = Amaz.Vector3f(1.0, 1.0, 1.0),
        ["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, 0.0)
    }, 
    {
        ["localScale"] = Amaz.Vector3f(0.01, 0.01, 0.01),
        ["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, 360.0)
    }, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
end

function Transform:seek(time)
    self.tween:set(time - self.tween1.duration * 0.8)
    self.tween1:set(time)
end

function Transform:setDuration(duration)
    self.tween.duration = duration * 0.2
    self.tween1.duration = duration
end

function Transform:clear()
    if self.tween then
        self.tween:set(0)
        self.tween:clear()
        self.tween = nil
    end
    if self.tween1 then
        self.tween1:set(0)
        self.tween1:clear()
        self.tween1 = nil
    end
end
exports.Transform = Transform
return exports
