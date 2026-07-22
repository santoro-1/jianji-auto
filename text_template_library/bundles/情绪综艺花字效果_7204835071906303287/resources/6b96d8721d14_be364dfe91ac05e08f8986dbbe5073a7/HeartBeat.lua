local exports = exports or {}
local HeartBeat = HeartBeat or {}
HeartBeat.__index = HeartBeat
function HeartBeat.new(construct, ...)
    local self = setmetatable({}, HeartBeat)
    self.tween = nil
    self.tween1 = nil
    self.duration = 0
    if construct and HeartBeat.constructor then HeartBeat.constructor(self, ...) end
    return self
end

function HeartBeat:constructor()

end

local function funcHeartBeat0(t, b, c, d)
    t = t / d
    if t < 1.0 / 4.0 then
        t = 32.0 / 3.0 * (t - 1.0 / 8.0) * (t - 1.0 / 8.0) - 1.0 / 6.0
    else
        t = -16.0 / 9.0 * (t - 1.0) * (t - 1.0) + 1.0
    end
    return c * t + b
end

local function funcHeartBeat1(t, b, c, d)
    t = t / d
    if t < 3.0 / 4.0 then
        t = 16.0 / 9.0 * t * t
    else
        t = -32.0 / 3.0 * (t - 7.0 / 8.0) * (t - 7.0 / 8.0) + 7.0 / 6.0
    end
    return c * t + b
end

function HeartBeat:onStart(comp)
    self.tween = comp.entity.scene.tween:fromTo(comp.entity:getComponent("Transform"), 
                                                {["localScale"] = Amaz.Vector3f(1.0, 1.0, 1.0) }, 
                                                {["localScale"] = Amaz.Vector3f(1.5, 1.5, 1.5) }, 
                                                0.1, 
                                                funcHeartBeat0, 
                                                nil, 
                                                0.0, 
                                                nil, 
                                                false)
    self.tween1 = comp.entity.scene.tween:fromTo(comp.entity:getComponent("Transform"), 
                                                {["localScale"] = Amaz.Vector3f(1.5, 1.5, 1.5) }, 
                                                {["localScale"] = Amaz.Vector3f(1.0, 1.0, 1.0) }, 
                                                0.1, 
                                                funcHeartBeat1, 
                                                nil, 
                                                0.0, 
                                                nil, 
                                                false)
end

function HeartBeat:seek(time)
    time = time % self.duration
    if(time <= self.tween.duration) then
        self.tween:set(time)
    else
        self.tween1:set(time - self.tween.duration)
    end
end

function HeartBeat:setDuration(duration)
    self.duration = duration
    self.tween.duration = duration / 2.0
    self.tween1.duration = duration - self.tween.duration
end

function HeartBeat:clear()
    if self.tween then
        self.tween:set(0)
        self.tween:clear()
        self.tween = nil
    end
    if self.tween1 then
        self.tween1:clear()
        self.tween1 = nil
    end
end
exports.HeartBeat = HeartBeat
return exports
