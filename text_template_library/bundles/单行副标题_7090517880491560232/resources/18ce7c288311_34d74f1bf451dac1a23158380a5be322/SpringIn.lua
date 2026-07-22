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
local SpringIn = SpringIn or {}
SpringIn.__index = SpringIn
function SpringIn.new(construct, ...)
    local self = setmetatable({}, SpringIn)
    self.duration = 1.0
    self.count = 0
    if construct and SpringIn.constructor then SpringIn.constructor(self, ...) end
    return self
end

function SpringIn:constructor()

end

function SpringIn:onStart(comp) 
	self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
	self.trans = comp.entity:getComponent("Transform")
	-- self.text.str = 'SpringIn'

	self.first = true
	self.renderer = nil
	if self.text ~= nil then
		-- self.sharedMaterial = comp.entity.scene.assetMgr:SyncLoad('material/rt.material')
		self.renderer = comp.entity:getComponent("MeshRenderer")
	else
		self.renderer = comp.entity:getComponent("Sprite2DRenderer")
	end
end

function SpringIn:animate()
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
			['scale'] = {0, 0, 0},
			-- ['scale.x'] = 0,
			-- ['scale.y'] = 0,
			-- ['scale.z'] = 0,
		},
		['animations'] = {
			-- 0 none 1 motion 2 scale
			['blurType'] = {
				{0, 1, 0, 0, {0, 0, 1, 1}},
			},
			['blurDirection'] = {
				{0, 1, {0, 1}, {0, 1}, {0, 0, 1, 1}}
			},
			['blurStep'] = {
				{0, 1, 1, 0, funcEaseBlurAction3},
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
				{0, 1, {0, 0, 0}, {1, 1, 1}, funcEaseAction3}
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
function SpringIn:animateChar(char)
	return {
		['mode'] = 0,
		['duration'] = .8,
		['anchor'] = {0, 0},
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
-- function SpringIn:onUpdate(comp, deltaTime)
-- 	time = time + deltaTime
-- 	if time >= self.duration + 1 then
-- 		time = 0
-- 	end
-- 	self:seek(time)
-- end

function SpringIn:seek(time)
	if self.first then
		if self.text ~= nil then
			self.text.renderToRT = true
			local materials = Amaz.Vector()
		    local InsMaterials = self.sharedMaterial:instantiate()
		    materials:pushBack(InsMaterials)
			self.renderer.materials = materials
			self.materials = materials
			self.materials:get(0):enableMacro('ANIMSEQ', 0)
		else
			self.materials:get(0):enableMacro('ANIMSEQ', 1)
		end
		self.first = false
	end

	-- time = time % self.duration
	-- text animation
	if self.text ~= nil then
		self.count = self.text.chars:size()
	
		for i = 1, self.count do
			local char = self.text.chars:get(i - 1)
			local info = self:animateChar(char)
			local nt = 0
			if info.mode == 0 then
				local late = 0
				if self.count > 1 then
					late = (1 - info.duration) / (self.count - 1) * (i - 1)
				end
				if time / self.duration >= late then
					nt = saturate((time / self.duration - late) / info.duration)
				end
			else
				local duration = Amaz.Ease.linear((self.count - i + 1) / self.count, 0, self.duration, 1)
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

function SpringIn:setDuration(duration)
   self.duration = duration
end


function SpringIn:resetData( ... )
	if self.text ~= nil then
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
		self.text.chars = chars
	end

	self.trans.localPosition = Amaz.Vector3f(0, 0, 0)
	self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
	self.trans.localScale = Amaz.Vector3f(1, 1, 1)
end

function SpringIn:clear()
	self:resetData()
	if self.text ~= nil then
    	self.text.renderToRT = false
		self.materials:get(0):enableMacro('ANIMSEQ', 0)
	end
	self.first = true
	
end


function SpringIn:onEnter()
	self.first = true
end


function SpringIn:onLeave()
	self:resetData()
	if self.text ~= nil then
    	self.text.renderToRT = false
		self.materials:get(0):enableMacro('ANIMSEQ', 0)
	end
	self.first = true
end
		
exports.SpringIn = SpringIn
return exports
