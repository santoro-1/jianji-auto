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

local function bezier(controls)
	return function (t, b, c, d)
		t = t/d
		local tvalue = getBezierTfromX(controls, t)
		local value =  getBezierValue(controls, tvalue)
		return b + c * value[2]
	end
end

local function funcEaseBlurAction1(t, b, c, d)
    t = t/d
    -- diyijieduandeweiyiquxian，beisaierquxianbanben
    local controls = {.05,.71,.61,.99}
    local tvalue = getBezierTfromX(controls, t)
    local deriva = getBezierDerivative(controls, tvalue)
    return math.abs(deriva[2] / deriva[1]) * c
end

local function funcEaseAction3(t, b, c, d)
    t= t/d
    -- diyijieduandeweiyiquxian，zhegeshigongshibanben
    if t~=0.0 and t~=1.0 then
        t = math.exp(-7.0 * t) * 1.0 * math.sin((t - 0.075) * (2.0*math.pi) / 0.3) + 1.0
    end
    return Amaz.Ease.linearFunc(t,c,b)
end

local function funcEaseBlurAction3(t, b, c, d)
    t=t/d
    -- diyijieduandemohuquxian，zhegeshigongshibanben
    t = math.abs(math.pow(2, -5.0 * t) * math.log(2) * math.sin(2.5 * math.pi * t - 0.5 * math.pi) + math.pow(2, -5.0 * t) * math.cos(2.5 * math.pi * t - 0.5 * math.pi))
    
    return c * t
end

local function clamp(min, max, value)
	return math.min(math.max(value, 0), 1)
end

local function saturate(value)
	return clamp(0, 1, value)
end

local function lerp(a, b, c)
	c = saturate(0, 1, c)
	return (1 - c) * a + c * b
end

local function lerpVector3(a, b, c)
	c = saturate(0, 1, c)
	return Amaz.Vector3f(
		lerp(a.x, b.x, c),
		lerp(a.y, b.y, c),
		lerp(a.z, b.z, c)
	)
end

local function remap(smin, smax, dmin, dmax, value)
	return (value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

local function remapClamped(smin, smax, dmin, dmax, value)
	return saturate(value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

local function remapVector3(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z)
	) 
end

local function remapVector4(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z),
		remap(smin.w, smax.w, dmin.w, dmax.w, value.w)
	) 
end

local function playAnimation(info, nt, setValue)
	for key, value in pairs(info.default) do
		setValue(key, value)
	end
	for key, value in pairs(info.animations) do
		for index, keyframe in pairs(value) do
			if nt >= keyframe[1] and nt <= keyframe[2] then
				local func
				if type(keyframe[5]) == 'function' then
					func = keyframe[5]
				elseif type(keyframe[5]) == 'table' and #keyframe[5] == 4 then
					func = bezier(keyframe[5])
				end
				if type(func) == 'function' then
					local t = nt - keyframe[1]
					if keyframe[6] then t = 1 - t end
					if type(keyframe[3]) == 'number' and type(keyframe[4]) == 'number' then
						setValue(key, func(t, keyframe[3], keyframe[4] - keyframe[3], keyframe[2] - keyframe[1]))
					elseif type(keyframe[3]) == 'table'
						and type(keyframe[4]) == 'table'
						and #keyframe[3] == #keyframe[4] then
						local values = {}
						for i = 1, #keyframe[3] do
							values[i] = func(t, keyframe[3][i], keyframe[4][i] - keyframe[3][i], keyframe[2] - keyframe[1])
						end
						setValue(key, values)
					end
				end
				break
			elseif nt < keyframe[1] then
				if index > 1 then
					local val = value[index - 1][4]
					if value[index - 1][6] then val = value[index - 1][3] end
					setValue(key, val)
				end
				break
			elseif nt > keyframe[2] then
				local val = value[index][4]
				if keyframe[6] then val = value[index][3] end
				setValue(key, val)
			end
		end
	end
end

local function anchor(pivot, anchor, halfWidth, halfHeight, translate, rotate, scale)
	local anchor = Amaz.Vector4f(
		remap(-.5, .5, 1, -1, pivot[1]) * halfWidth + remap(-.5, .5, -(1 - scale.x), 1 - scale.x, anchor[1]) * halfWidth,
		remap(-.5, .5, 1, -1, pivot[2]) * halfHeight + remap(-.5, .5, -(1 - scale.y), 1 - scale.y, anchor[2]) * halfHeight,
		0,
		1
	)
	local mat = Amaz.Matrix4x4f()
	mat:setTRS(
		Amaz.Vector3f(
			remap(-.5, .5, -1, 1, pivot[1]) * halfWidth,
			remap(-.5, .5, -1, 1, pivot[2]) * halfHeight,
			0
		),
		Amaz.Quaternionf.eulerToQuaternion(Amaz.Vector3f(rotate.x / 180 * math.pi, rotate.y / 180 * math.pi, rotate.z / 180 * math.pi)),
		Amaz.Vector3f(1, 1, 1)
	)
	anchor = mat:multiplyVector4(anchor)
	return Amaz.Vector3f(anchor.x, anchor.y, anchor.z) + translate, rotate, scale
end

local exports = exports or {}
local T7135428706043003265 = T7135428706043003265 or {}
T7135428706043003265.__index = T7135428706043003265
function T7135428706043003265.new(construct, ...)
    local self = setmetatable({}, T7135428706043003265)
    self.duration = 2.0
    self.count = 0
    if construct and T7135428706043003265.constructor then T7135428706043003265.constructor(self, ...) end
    return self
end

function T7135428706043003265:constructor()

end

function T7135428706043003265:onStart(comp)
	self.text = comp.entity:getComponent("SDFText")
	self.trans = comp.entity:getComponent("Transform")
	-- self.text.str = 'Transform'
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
	end
	
	self.first = true
	self.renderer = nil
	if self.text ~= nil then
		self.renderer = comp.entity:getComponent("MeshRenderer")
	else
		self.renderer = comp.entity:getComponent("Sprite2DRenderer")
	end
end

function T7135428706043003265:animate()
	return {
		-- ['playSpeed'] = 30,
		['anchor'] = {0, 0},
		['pivot'] = {0, 0},
		['default'] = {
			['blurType'] = 0,
            ['blurDirection'] = {0, 1},
            ['blurStep'] = 0,
			['translate'] = {0, 0, 0},
			-- ['translate.x'] = 0,
			-- ['translate.y'] = 0,
			-- ['translate.z'] = 0,
			['rotate'] = {0, 0, 0},
			-- ['rotate.x'] = 0,
			-- ['rotate.y'] = 0,
			-- ['rotate.z'] = 0,
			['scale'] = {1, 1, 1},
			-- ['scale.x'] = 0,
			-- ['scale.y'] = 0,
			-- ['scale.z'] = 0,
		},
		['animations'] = {
			-- 0 none 1 motion 2 scale
			['blurType'] = {
			},
			['blurDirection'] = {
			},
			['blurStep'] = {
			},
			['translate'] = {
			},
			['translate.x'] = {
			},
			['translate.y'] = {
			},
			['translate.z'] = {
			},
			['rotate'] = {
			},
			['rotate.x'] = {
			},
			['rotate.y'] = {
			},
			['rotate.z'] = {
			},
			['scale'] = {
			},
			['scale.x'] = {
			},
			['scale.y'] = {
			},
			['scale.z'] = {
			}
		}
	}
end

-- startTime endTime startValue endValue easeFunction
-- mode: 0 same duration per char, 1 not same duration per char
-- duration: ratio of char animation and total time, only enable when mode is 0
function T7135428706043003265:animateChar(char)
	return {
		['mode'] = 0,
		['duration'] = 1.0,
		['anchor'] = {0, -0.5},
		['pivot'] = {0, 0},
		['default'] = {
			['translate'] = {0, 0, 0},
			-- ['translate.x'] = 0,
			-- ['translate.y'] = 0,
			-- ['translate.z'] = 0,
			['rotate'] = {0, 0, 0},
			-- ['rotate.x'] = 0,
			-- ['rotate.y'] = 0,
			-- ['rotate.z'] = 0,
			['scale'] = {1, 1, 1},
			-- ['scale.x'] = 0,
			-- ['scale.y'] = 0,
			-- ['scale.z'] = 0,
			['color'] = {1, 1, 1, 1},
			-- ['color.x'] = 1,
			-- ['color.y'] = 1,
			-- ['color.z'] = 1,
			-- ['color.w'] = 1,
		},
		['animations'] = {
			['translate'] = {
			},
			['translate.x'] = {
			},
			['translate.y'] = {
			},
			['translate.z'] = {
			},
			['rotate'] = {
			},
			['rotate.x'] = {
			},
			['rotate.y'] = {
			},
			['rotate.z'] = {
			},
			['scale'] = {
				{ 0, 0.5, {1, 1, 1}, {1.2, 1.2, 1.2}, Amaz.Ease.linear},
				{ 0.5, 1, {1.2, 1.2, 1.2}, {1, 1, 1}, Amaz.Ease.linear}
			},
			['scale.x'] = {
			},
			['scale.y'] = {
			},
			['scale.z'] = {
			},
			['color'] = {
			},
			['color.x'] = {
			},
			['color.y'] = {
			},
			['color.z'] = {
			},
			['color.w'] = {
			},
		}
	}
end

-- local time = 0
-- function T7135428706043003265:onUpdate(comp, deltaTime)
-- 	time = time + deltaTime
-- 	if time >= self.duration + 1 then
-- 		time = 0
-- 	end
-- 	self:seek(time)
-- end

function T7135428706043003265:seek(time)
	if self.first then
		local materials = Amaz.Vector()
		materials:pushBack(self.sharedMaterial)
		self.renderer.sharedMaterials = materials
		self.materials = self.renderer.materials
		if self.text ~= nil then
			self.text.renderToRT = true
			self.materials:get(0):enableMacro('ANIMSEQ', 0)
		else
			self.materials:get(0):enableMacro('ANIMSEQ', 1)
		end
		self.first = false
	else
		self.renderer.materials = self.materials
	end

	time = time % self.duration

	-- text animation
	if self.text ~= nil then
		self.count = self.text.chars:size()

		local offset = 0
		for i = 1, self.count do
			local code = self.text.chars:get(i - 1).utf8code
			if code == ' ' or code == '　' or code == '\r' or code == '\n'  then
				offset = offset + 1
			end
		end

		local charDuration = 1 / (self.count + 1 - offset)

		offset = 0
		for i = 1, self.count do
			local char = self.text.chars:get(i - 1)
			
			local code = char.utf8code
			if code == ' ' or code == '　' or code == '\r' or code == '\n'  then
				offset = offset + 1
			else
				local info = self:animateChar(char)
				local nt = 0
				local index = i - offset
				if info.mode == 0 then
					local late = 0
					if self.count > 1 then
						late = (1 - charDuration) / (self.count) * (index - 1)
					end
					if time / self.duration >= late then
						nt = saturate((time / self.duration - late) / charDuration)
					end
					if self.count > 10 and nt> 0.1 and nt < 0.9999 then
						nt = 0.5
					end
				else
					local duration = Amaz.Ease.linear((self.count - index + 1) / self.count, 0, self.duration, 1)
					nt = (time - (self.duration - duration)) / duration
				end
	
				local translate = Amaz.Vector3f()
				local rotate = Amaz.Vector3f()
				local scale = Amaz.Vector3f()
				local color = Amaz.Vector4f()
				playAnimation(info, nt, function (key, value)
					if key == 'translate.x' then
						translate.x = value
					elseif key == 'translate.y' then
						translate.y = value
					elseif key == 'translate.z' then
						translate.z = value
					elseif key == 'translate' and type(value) == 'table' then
						translate:set(value[1], value[2], value[3])
					elseif key == 'rotate.x' then
						rotate.x = value
					elseif key == 'rotate.y' then
						rotate.y = value
					elseif key == 'rotate.z' then
						rotate.z = value
					elseif key == 'rotate' and type(value) == 'table' then
						rotate:set(value[1], value[2], value[3])
					elseif key == 'scale.x' then
						scale.x = value
					elseif key == 'scale.y' then
						scale.y = value
					elseif key == 'scale.z' then
						scale.z = value
					elseif key == 'scale' and type(value) == 'table' then
						scale:set(value[1], value[2], value[3])
					elseif key == 'color.x' then
						color.x = value
					elseif key == 'color.y' then
						color.y = value
					elseif key == 'color.z' then
						color.z = value
					elseif key == 'color.w' then
						color.w = value
					elseif key == 'color' and type(value) == 'table' then
						color:set(value[1], value[2], value[3], value[4])
					end
				end)
		
				translate, rotate, scale = anchor(info['pivot'], info['anchor'], char.width / 3, char.height / 3, translate, rotate, scale)
				char.position = char.initialPosition + translate
				char.rotate = rotate
				char.scale = scale
				char.color = color
			end
		end
	
		local chars = self.text.chars 
		self.text.chars= chars
	end

	local info = self:animate()
	local translate = Amaz.Vector3f()
	local rotate = Amaz.Vector3f()
	local scale = Amaz.Vector3f()
	-- local realTime = time - time % (1 / info.playSpeed)
	playAnimation(info, time / self.duration, function (key, value)
		if key == 'translate.x' then
			translate.x = value
		elseif key == 'translate.y' then
			translate.y = value
		elseif key == 'translate.z' then
			translate.z = value
		elseif key == 'translate' and type(value) == 'table' then
			translate:set(value[1], value[2], value[3])
		elseif key == 'rotate.x' then
			rotate.x = value
		elseif key == 'rotate.y' then
			rotate.y = value
		elseif key == 'rotate.z' then
			rotate.z = value
		elseif key == 'rotate' and type(value) == 'table' then
			rotate:set(value[1], value[2], value[3])
		elseif key == 'scale.x' then
			scale.x = value
		elseif key == 'scale.y' then
			scale.y = value
		elseif key == 'scale.z' then
			scale.z = value
		elseif key == 'scale' and type(value) == 'table' then
			scale:set(value[1], value[2], value[3])
		elseif key == 'blurType' then
            self.materials:get(0):enableMacro('BLUR_TYPE', value)
        elseif key == 'blurDirection' then
            self.materials:get(0):setVec2('blurDirection', Amaz.Vector2f(value[1], value[2]))
        elseif key == 'blurStep' then
			self.materials:get(0):setFloat('blurStep', value)
		elseif key == 'alpha' then
            self.materials:get(0):setFloat('alpha', value)
		end
	end)

	local halfOutputHeight = Amaz.BuiltinObject:getOutputTextureHeight() / 2
	local halfWidth = 0
	local halfHeight = 0
	if self.text ~= nil then
		halfWidth = (self.text.rect.width - self.text.rect.x) / 2 / halfOutputHeight
		halfHeight = (self.text.rect.height - self.text.rect.y) / 2 / halfOutputHeight
	else
		local size = self.renderer:getTextureSize()
		halfWidth = size.x / 2 / halfOutputHeight
		halfHeight = size.y / 2 / halfOutputHeight
	end
	translate, rotate, scale = anchor(info['pivot'], info['anchor'], halfWidth, halfHeight, translate, rotate, scale)

	self.trans.localPosition = translate
	self.trans.localEulerAngle = rotate
	self.trans.localScale = scale
end

function T7135428706043003265:setDuration(duration)
   self.duration = duration
end

function T7135428706043003265:resetData()
	if self.text ~= nil and not self.clearState  then
		for i = 1, self.text.chars:size() do
			local char = self.text.chars:get(i - 1)
			if char.rowth ~= -1 then
				char.position = char.initialPosition
				char.rotate = Amaz.Vector3f(0, 0, 0)
				char.scale = Amaz.Vector3f(1, 1, 1)
				char.color = Amaz.Vector4f(1, 1, 1, 1)
			end
		end
    	local chars = self.text.chars 
		self.text.chars= chars
		self.clearState = true
		self.text.renderToRT = false
		self.sharedMaterial:enableMacro('ANIMSEQ', 0)
		self.renderer.sharedMaterials = Amaz.Vector()
	end

	self.trans.localPosition = Amaz.Vector3f(0, 0, 0)
	self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
	self.trans.localScale = Amaz.Vector3f(1, 1, 1)
end

function T7135428706043003265:clear()
	self:resetData()
end


function T7135428706043003265:onEnter()
	self.first = true
	self.clearState = false
	-- self.text.renderToRT = true
end


function T7135428706043003265:onLeave()
	if self.text ~= nil and not self.clearState then
		self:resetData()
	end
	self.first = true
end

exports.T7135428706043003265 = T7135428706043003265
return exports
