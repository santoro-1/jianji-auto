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

function TextAnim:onStart(comp) 
	self.text = comp.entity:getComponent("SDFText")
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    self.renderer = comp.entity:getComponent("MeshRenderer")
    self.first = true
    self:seek(0)
end

function TextAnim:initAnim()
    self.text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = self.sharedMaterial:instantiate()
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials
    -- self:seek(0)
end

function TextAnim:seek(time)
    if self.first then
        self:initAnim()
        self.first = false
    end
    
    self.text.renderToRT = true
    self.renderer.materials = self.materials
    --local controls = {0.35,0.74,0.35,0.86}
    local t = time / self.duration
    --local tvalue = getBezierTfromX(controls, t)
    --local value = getBezierValue(controls, tvalue)[2]
    self.materials:get(0):setFloat("_time",t)
    local mat = self.materials:get(0)
    local tex = mat:getTex('_MainTex')
    if tex then
        mat:setVec4('texSize', Amaz.Vector4f(tex.width, tex.height, 0, 0))
        Amaz.LOGI('RT Size w(lua): ', tex.width)
        Amaz.LOGI('RT Size h(lua): ', tex.height)
    end
    if self.text ~= nil then
		if self.text.typeSettingKind == 0 then
			self.renderer.material:setFloat("flag", 0)
		else
	
			self.renderer.material:setFloat("flag", 1.0)
		end
	end
end
-- function TextAnim:onUpdate() 
-- 	local mat = self.materials:get(0)
--     local tex = mat:getTex('_MainTex')
--     if tex then
--         mat:setVec4('texSize', Amaz.Vector4f(tex.width, tex.height, 0, 0))
--     end
-- end
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
