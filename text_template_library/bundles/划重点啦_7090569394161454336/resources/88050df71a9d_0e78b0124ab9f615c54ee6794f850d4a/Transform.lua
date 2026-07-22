local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
    local self = setmetatable({}, Transform)
    self.duration = 0.0
    self.radius = 0.07
    self.speed = 9.0
    self.deltaTime = 0.0
    self.lastTime = 0.0
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end

function Transform:onStart(comp)
    self.transform = comp.entity:getComponent("Transform")
end

function Transform:seek(time)
    
    if self.lastTime == 0.0 then
        self.lastTime = time
    end
    
    local screenW = Amaz.BuiltinObject:getOutputTextureWidth();
    local screenH = Amaz.BuiltinObject:getOutputTextureHeight();
    self.deltaTime = self.deltaTime + math.abs(time - self.lastTime)
    self.lastTime = time

    if self.deltaTime > self.duration / self.speed then
        self.deltaTime = 0.0
        -- math.randomseed(time % self.duration)
        local rand = math.random()
        local r = 2 * math.pi * rand
        local distance = self.radius * rand * 720 / math.min(screenH, screenW)
        local x = distance * math.sin(r)
        local y = distance * math.cos(r)

        self.transform.localPosition = Amaz.Vector3f(x, y, 0)
    end
end

function Transform:setDuration(duration)
    self.duration = duration
    self.deltaTime = 0.0
    self.lastTime = 0.0
end

function Transform:clear()
    self.transform.localPosition = Amaz.Vector3f(0, 0, 0)
    self.deltaTime = 0.0
    self.lastTime = 0.0
end
exports.Transform = Transform
return exports
