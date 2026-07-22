-- Use requireFile to include other lua modules within the same folder
function requireFile(comp, fileName)
    local path = comp.assetMgr.rootDir
    local modulePath = path.."lua/"
    package.path = package.path..";"..modulePath.."?.lua"
    return require(fileName)
end

local exports = exports or {}
local AnimScript = AnimScript or {}

---@class AnimScript : ScriptComponent
---@field duration number
---@field progress number [UI(Range={0.0, 1.0}, Slider)]
---@field autoPlay boolean
---@field effectMaterial Material
AnimScript.__index = AnimScript


local AETools = AETools or {}
AETools.__index = AETools

function AETools:new(attrs)
    local self = setmetatable({}, AETools)
    self.attrs = attrs

    local max_frame = 0
    for _,v in pairs(attrs) do
        for i = 1, #v do
            local content = v[i]
            local cur_frame = content[2][2]
            max_frame = math.max(cur_frame, max_frame)
        end
    end
    self:SetAllFrame(max_frame)

    return self
end

function AETools._remap01(a,b,x)
    if x < a then return 0 end
    if x > b then return 1 end
    return (x-a)/(b-a)
end

function AETools._cubicBezier(p1, p2, p3, p4, t)
    return {
        p1[1]*(1.-t)*(1.-t)*(1.-t) + 3*p2[1]*(1.-t)*(1.-t)*t + 3*p3[1]*(1.-t)*t*t + p4[1]*t*t*t,
        p1[2]*(1.-t)*(1.-t)*(1.-t) + 3*p2[2]*(1.-t)*(1.-t)*t + 3*p3[2]*(1.-t)*t*t + p4[2]*t*t*t,
    }
end

function AETools:_cubicBezier01(_bezier_val, p)
    local x = self:_getBezier01X(_bezier_val, p)
    return self._cubicBezier(
        {0,0},
        {_bezier_val[1], _bezier_val[2]},
        {_bezier_val[3], _bezier_val[4]},
        {1,1},
        x
    )[2]
end

function AETools:_getBezier01X(_bezier_val, x)
    local ts = 0
    local te = 1
    -- divide and conque
    repeat
        local tm = (ts+te)*0.5
        local value = self._cubicBezier(
            {0,0},
            {_bezier_val[1], _bezier_val[2]},
            {_bezier_val[3], _bezier_val[4]},
            {1,1},
            tm)
        if(value[1]>x) then
            te = tm
        else
            ts = tm
        end
    until(te-ts < 0.0001)

    return (te+ts)*0.5
end

function AETools._mix(a, b, x)
    return a * (1-x) + b * x
end

function AETools:SetAllFrame(val)
    self.all_frame = val
end

function AETools:GetVal(_name, _progress)
    local content = self.attrs[_name]
    if content == nil then
        return nil
    end

    local cur_frame = _progress * self.all_frame

    for i = 1, #content do
        local info = content[i]
        local start_frame = info[2][1]
        local end_frame = info[2][2]
        if cur_frame >= start_frame and cur_frame < end_frame then
            local cur_progress = self._remap01(start_frame, end_frame, cur_frame)
            local bezier = info[1]
            local value_range = info[3]

            local p = self:_cubicBezier01(bezier, cur_progress)

            if type(value_range[1]) == "table" then
                local res = {}
                for j = 1, #value_range[1] do
                    res[j] = self._mix(value_range[1][j], value_range[2][j], p)
                end
                return res
            end
            return self._mix(value_range[1], value_range[2], p)
        end
    end

    local first_info = content[1]
    local start_frame = first_info[2][1]
    if cur_frame<start_frame then
        return first_info[3][1]
    end

    local last_info = content[#content]
    local end_frame = last_info[2][2]
    if cur_frame>=end_frame then
        return last_info[3][2]
    end

end

function AETools:test()
    Amaz.LOGI("lrc "..tostring(self.key_frame_info), tostring(#self.key_frame_info))
end




local ae_attribute = {
	["Text_Tracking_Amount"]={
		{{0.000130064, 0.000013607, 0, 0.843811083, }, {0, 10.00001, }, {{-30, }, {5, }, }, }, 
		{{0.0001, 0.00019284, 0.622021277, 0.999999981, }, {10.00001, 89.000091, }, {{5, }, {20, }, }, }, 
	}, 
	["Scale"]={
		{{0.00237599, 0.00031144,0.001174235,0.92172832, }, {0, 10.00001, }, {{0, 0, 100, }, {85, 85, 100, }, }, }, 
		{{0.0001,-0.000004968,0.568778848,0.999999933,}, {10.00001, 89.000091, }, {{85, 85, 100, }, {100, 100, 100, }, }, }, 
	}, 
	["Rotate"]={
		{{0.000170431, 0.000027637, 0.000079768, 0.897029852, }, {0, 10.00001, }, {{15, }, {5, }, }, }, 
		{{0.0001, 0, 0.574949174, 1.000000034, }, {10.00001, 89.000091, }, {{5, }, {0, }, }, }, 
	}, 
	["Radial_Blur_Amount"]={
		{{0.166666667, 0.166666667, 0.66666667, 1, }, {1.000001, 8.000008, }, {{75, }, {0, }, }, }, 
		{{0.166666667, 0.166666667, 0.66666667, 1, }, {8.000008, 89.000091, }, {{0, }, {0, }, }, }, 
	}, 
}

function AnimScript:initKeyFrame(table_name, attr_table, fps) 
    for _name, info_list in pairs(attr_table) do
        local tool = AETools:new(fps)
        for i = 1, #info_list do
            tool:addKeyFrameInfo(info_list[i][1], info_list[i][2], info_list[i][3], info_list[i][4])
        end
        if self[table_name] == nil then
            self[table_name] = {}
        end
        self[table_name][_name] = tool
    end
end
function AnimScript.new()
    local self = {}
    setmetatable(self, AnimScript)
    self.first = true
    self.duration = 1.0
    self.curTime = 0.0
    self.progress = 0
    self.autoPlay = false
    self.effectMaterial = nil
    self.wordGap = 0
    self.incGap = 0
    return self
end
function AnimScript:setMatToSDFText()

    self.text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = nil
    if self.effectMaterial then
        InsMaterials = self.effectMaterial:instantiate()
    else
        InsMaterials = self.renderer.material
    end
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials

    self.material = self.renderer.material
end

---@param comp Component
function AnimScript:onStart(comp)
    -- Amaz.LOGE("AnimScript", "onStart")
    self.first = true
    self.text = comp.entity:getComponent('SDFText')
    self.trans = comp.entity:getComponent('Transform')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
            self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    self.renderer = nil
	if self.text ~= nil then
		self.renderer = comp.entity:getComponent("MeshRenderer")
	else
		self.renderer = comp.entity:getComponent("Sprite2DRenderer")
	end
    self.attr = AETools:new(ae_attribute)
    self.wordGap = self.text.wordGap
end

local function remap01(a,b,x)
    if x < a then return 0 end
    if x > b then return 1 end
    return (x-a)/(b-a)
end
local function clamp(min, max, value)
	return math.min(math.max(value, min), max)
end
---@param comp Component
---@param deltaTime number
function AnimScript:onUpdate(comp, deltaTime)
    if Amaz.Macros and Amaz.Macros.EditorSDK then
        if self.autoPlay then
            self.curTime = self.curTime + deltaTime
        end
        self:seek(self.curTime)

    else
        self.curTime = 0
    end
end

function AnimScript:seek(time)
    if Amaz.Macros and Amaz.Macros.EditorSDK then
        if self.autoPlay then
            self.progress = (time % self.duration) / self.duration
        end
    else
        self.progress = clamp(0, 1, (time) / math.min(self.duration, 3.0))
    end
    if self.first == true then
        self:setMatToSDFText()
        self.first = false
    end

    local wordGap = self.attr:GetVal("Text_Tracking_Amount", self.progress)[1] * 0.01
    self.text.wordGap = wordGap + self.wordGap
    self.incGap = wordGap
    local scale = self.attr:GetVal("Scale", self.progress)[1] * 0.01
    local rotate = self.attr:GetVal("Rotate", self.progress)[1]
    self.trans.localScale = Amaz.Vector3f(scale, scale, 1)
    self.trans.localEulerAngle = Amaz.Vector3f(0, 0, -rotate)
    local amount = self.attr:GetVal("Radial_Blur_Amount", self.progress)[1]
    self.material:setFloat("u_Amount", amount)
    self.text.targetRTExtraSize = Amaz.Vector2f(self.text.rect.width * amount * 0.01 * 0.5, self.text.rect.height * amount * 0.01 * 0.5)

end



function AnimScript:onEnter()
	self.first = true
	
end
function AnimScript:resetData( ... )
	if self.text ~= nil then
    	local chars = self.text.chars 
		for i = 1, self.text.chars:size() do
			local char = chars:get(i - 1)
			if char.rowth ~= -1 then
				char.position = char.initialPosition
				char.rotate = Amaz.Vector3f(0, 0, 0)
				char.scale = Amaz.Vector3f(1, 1, 1)
				char.color = Amaz.Vector4f(1, 1, 1, 1)
			end
		end
        self.text.renderToRT = false
        self.text.chars = chars
        self.trans.localScale = Amaz.Vector3f(1, 1, 1)
        self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
        if math.abs((self.wordGap + self.incGap) - self.text.wordGap) <= 0.001 then
            self.text.wordGap = self.wordGap
        end
	end
    self.text.targetRTExtraSize = Amaz.Vector2f(0.0, 0.0)

end

function AnimScript:setDuration(duration)
   self.duration = duration
end
function AnimScript:onLeave()
    self:resetData()
	self.first = true
end
function AnimScript:clear()

	self:resetData()
end

exports.AnimScript = AnimScript
return exports
