local function getBezierValue(controls, t)
    local ret = {}
    local xc1 = controls[1]
    local yc1 = controls[2]
    local xc2 = controls[3]
    local yc2 = controls[4]
    ret[1] = 3*xc1*(1-t)*(1-t)*t+3*xc2*(1-t)*t*t+t*t*t
    ret[2] = 3*yc1*(1-t)*(1-t)*t+3*yc2*(1-t)*t*t+t*t*t
    return ret
end

local function getBezierDerivative(controls, t)
    local ret = {}
    local xc1 = controls[1]
    local yc1 = controls[2]
    local xc2 = controls[3]
    local yc2 = controls[4]
    ret[1] = 3*xc1*(1-t)*(1-3*t)+3*xc2*(2-3*t)*t+3*t*t
    ret[2] = 3*yc1*(1-t)*(1-3*t)+3*yc2*(2-3*t)*t+3*t*t
    return ret
end

local function getBezierTfromX(controls, x)
    local ts = 0
    local te = 1
    -- divide and conque
    repeat
        local tm = (ts+te)/2
        local value = getBezierValue(controls, tm)
        if(value[1]>x) then
            te = tm
        else
            ts = tm
        end
    until(te-ts < 0.0001)

    return (te+ts)/2
end
local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)
    self.sharedMaterial = nil
	self.materials = nil
    self.renderer = nil
    self.isVertical = 0.0
    self.duration = 0
    self.first = true
    self.lasttime = 0.0
    self.length = 0.45
    if construct and TextAnim.constructor then TextAnim.constructor(self, ...) end
    return self
end

function TextAnim:constructor()

end

local function QuadraticFunction(centerTime, param)
    local c = param.x
    local a = (param.y - c) / (centerTime * centerTime - centerTime)
    local b = -a
    return function(nowTime)
        return a * nowTime * nowTime + b * nowTime + c
    end
end

local function bezier(controls)
    return function(t, b, c, d)
        t = t / d
        local tvalue = getBezierTfromX(controls, t)
        local value = getBezierValue(controls, tvalue)
        return b + c * value[2]
    end
end

function TextAnim:onStart(comp) 
--Amaz.LOGI('yyb ',23)
	self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    self.renderer = comp.entity:getComponent("MeshRenderer")
    self.first = true
    self.centerTime = 0.5
    self.positionBezier = bezier({.36,.2,.63,.83})
    self.blackFunc = QuadraticFunction(self.centerTime, self.blackCurve)

end

function TextAnim:initAnim()
    self.text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = self.sharedMaterial:instantiate()
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials
    self.material = self.renderer.materials:get(0)
end

function TextAnim:seek(time)
    if self.first then
        self:initAnim()
        self.first = false
    end
    
    self.text.renderToRT = true
    self.renderer.materials = self.materials
    self.material = self.renderer.materials:get(0)

    local nowTime = (time%(self.duration+0.000001)) / (self.duration+0.00001)

    if nowTime < self.blackCurve.z then
        self.material["u_blackRange"] = self.blackCurve.x
    elseif nowTime > self.blackCurve.z and nowTime<self.blackCurve.w then
        self.material["u_blackRange"] = self.blackCurve.x + (self.blackCurve.y-self.blackCurve.x)*(nowTime-self.blackCurve.z)/(self.blackCurve.w-self.blackCurve.z)
    elseif nowTime > self.blackCurve.w and nowTime<self.blackCurve1.x then
        self.material["u_blackRange"] = self.blackCurve.y
    elseif nowTime > self.blackCurve1.x and nowTime<self.blackCurve1.y then
        self.material["u_blackRange"] = self.blackCurve.y + (self.blackCurve.x-self.blackCurve.y)*(nowTime-self.blackCurve1.x)/(self.blackCurve1.y-self.blackCurve1.x)
    else
        self.material["u_blackRange"] = self.blackCurve.x
    end
    if nowTime < self.lineCurve.z then
        self.material["u_lineScale"] = self.lineCurve.x
    elseif nowTime > self.lineCurve.z and nowTime<self.lineCurve.w then
        self.material["u_lineScale"] = self.lineCurve.x + (self.lineCurve.y-self.lineCurve.x)*(nowTime-self.lineCurve.z)/(self.lineCurve.w-self.lineCurve.z)
    elseif nowTime > self.lineCurve.w and nowTime<self.lineCurve1.x then
        self.material["u_lineScale"] = self.lineCurve.y
    elseif nowTime > self.lineCurve1.x and nowTime<self.lineCurve1.y then
        self.material["u_lineScale"] = self.lineCurve.y + (self.lineCurve.x-self.lineCurve.y)*(nowTime-self.lineCurve1.x)/(self.lineCurve1.y-self.lineCurve1.x)
    else
        self.material["u_lineScale"] = self.lineCurve.x
    end
    self.material["u_uvOffset"] = self.positionBezier(nowTime,-0.5,1,1)
    self.material["u_angle"] = self.angle
    self.material["u_colorChange"] = self.colorChange
    self.material["u_blackSmoothRange"] = self.smoothRange / 10
end

function TextAnim:setDuration(duration)
    self.duration = duration
end

function TextAnim:clear()
    if self.text then
        self.text.renderToRT = false
    end
end


function TextAnim:onEnter()
    self.first = true
end

function TextAnim:onLeave()
    if self.text then
        self.text.renderToRT = false
    end
    self.first = true
end

exports.TextAnim = TextAnim
return exports
