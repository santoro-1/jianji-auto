local exports = exports or {}
local Rotate = Rotate or {}
Rotate.__index = Rotate
function Rotate.new(construct, ...)
    local self = setmetatable({}, Rotate)
    self.text = nil
    self.tween = nil
    self.tween1 = nil
    self.tween2 = nil
    self.duration = 0
    if construct and Rotate.constructor then Rotate.constructor(self, ...) end
    return self
end

function Rotate:constructor()

end

function Rotate:onStart(comp)
    local transform = comp.entity:getComponent("Transform")
    self.tween = comp.entity.scene.tween:fromTo(transform, 
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, 0.0)},
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, -15.0)}, 
                                                0.1, 
                                                Amaz.Ease.linear, 
                                                nil, 
                                                0.0, 
                                                nil, 
                                                false)
    self.tween1 = comp.entity.scene.tween:fromTo(transform, 
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, -15.0)},
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, 15.0)}, 
                                                0.1, 
                                                Amaz.Ease.linear, 
                                                nil, 
                                                0.0, 
                                                nil, 
                                                false)
 
    self.tween2 = comp.entity.scene.tween:fromTo(transform, 
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, 15.0)},
                                                {["localEulerAngle"] = Amaz.Vector3f(0.0, 0.0, 0.0)}, 
                                                0.1, 
                                                Amaz.Ease.linear, 
                                                nil, 
                                                0.0, 
                                                nil, 
                                                false)
end

function Rotate:seek(time)
    time = time % self.duration
    if(time <= self.tween.duration) then
        self.tween:set(time)
    elseif(time <= self.tween.duration + self.tween1.duration) then
        self.tween1:set(time - self.tween.duration)
    else
        self.tween2:set(time - self.tween.duration - self.tween1.duration)
    end
end

function Rotate:setDuration(duration)
    self.duration = duration
    self.tween1.duration = duration / 2.0
    self.tween.duration = (duration - self.tween1.duration) / 2.0
    self.tween2.duration = duration - self.tween1.duration - self.tween.duration
end

function Rotate:clear()
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
exports.Rotate = Rotate
return exports
