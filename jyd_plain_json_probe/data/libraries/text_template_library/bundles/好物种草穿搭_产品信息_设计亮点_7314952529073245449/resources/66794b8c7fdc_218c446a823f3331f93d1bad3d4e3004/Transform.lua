local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
    local self = setmetatable({}, Transform)
    self.text = nil
    self.tween = nil
    self.tween1 = nil
    self.tween2 = nil
    self.duration = 0
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end

function Transform:onStart(comp)
    local transform = comp.entity:getComponent("Transform")
    self.tween = comp.entity.scene.tween:fromTo(transform, 
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, 0.0)},
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, -360.0)}, 
                                                0.1, 
                                                Amaz.Ease.linear, 
                                                nil, 
                                                0.0, 
                                                nil, 
                                                false)
end

function Transform:seek(time)
    time = time % self.duration
    self.tween:set(time)
end

function Transform:setDuration(duration)
    self.duration = duration
    self.tween.duration = duration
end

function Transform:clear()
    if self.tween then
        self.tween:set(0)
        self.tween:clear()
        self.tween = nil
    end
    if self.tween1 then
        self.tween1:clear()
        self.tween1 = nil
    end
    if self.tween2 then
        self.tween2:clear()
        self.tween2 = nil
    end
end
exports.Transform = Transform
return exports
