--@input float duration = 0.0{"widget":"slider","min":0.1,"max":2.0}
--@input float curtime = 0.0{"widget":"slider","min":0.0,"max":3.0}
--@input float firstTime = 0.6{"widget":"slider","min":0.1,"max":1.0}
--@input float delayFactor = 1.0{"widget":"slider","min":0.0,"max":1.0}
local delayFactor = 1.0
local firstTime = 0.6
local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
    local self = setmetatable({}, Transform)
    self.duration = 1.0
    self.count = 0
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end


function Transform:onStart(comp) 
	self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
end

-- -- config for editor
-- local editor = {
-- 	enable = true,
-- 	time = 0,
-- }
-- -- used for editor simulate
-- function Transform:onUpdate(comp, deltaTime)
-- 	if editor.enable then
-- 		local properties = comp.properties
-- 		if properties:has('duration') then
-- 			local duration = properties:get('duration')
-- 			self:setDuration(duration)
-- 		end
-- 		if properties:has('curtime') then
-- 			local curtime = properties:get('curtime')
-- 			self:seek(curtime)
-- 		end
-- 		if properties:has('delayFactor') then
-- 			delayFactor = properties:get('delayFactor')
-- 		end
-- 		if properties:has('firstTime') then
-- 			firstTime = properties:get('firstTime')
-- 		end
-- 		-- self:seek(editor.time)
-- 		-- editor.time = (editor.time + deltaTime) % 3
-- 	end
-- end

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
	--[0,d] ~ [b,b+c],tdaibiaodangqianxzhi
	return function (t, b, c, d)
		t = t/d
		local tvalue = getBezierTfromX(controls, t)
		local value =  getBezierValue(controls, tvalue)
		return b + c * value[2]
	end
end

function clamp(min, max, value)
	return math.min(math.max(value, 0), 1)
end

function saturate(value)
	return clamp(0, 1, value)
end

function lerp(a, b, c)
	c = saturate(0, 1, c)
	return (1 - c) * a + c * b
end

function lerpVector3(a, b, c)
	c = saturate(0, 1, c)
	return Amaz.Vector3f(
		lerp(a.x, b.x, c),
		lerp(a.y, b.y, c),
		lerp(a.z, b.z, c)
	)
end

function remap(smin, smax, dmin, dmax, value)
	return (value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

function remapClamped(smin, smax, dmin, dmax, value)
	return saturate(value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

function remapVector3(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z)
	) 
end

function remapVector4(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z),
		remap(smin.w, smax.w, dmin.w, dmax.w, value.w)
	) 
end

-- startTime endTime startValue endValue easeFunction
-- mode: 0 same duration per char, 1 not same duration per char
-- duration: ratio of char animation and total time, only enable when mode is 0
local function animate(char, total)
	return {
		['mode'] = 0,
		['duration'] = firstTime,
		['anchor'] = {0, -0.5},
		['pivot'] = {0, 0},
		['default'] = {
			-- ['scale.x'] = 0,
			-- ['scale.y'] = 0,
			-- ['scale.z'] = 0,
			['scale'] = {0, 0, 0},
			-- ['rotate.x'] = 0,
			-- ['rotate.y'] = 0,
			['rotate.z'] = 0,
			-- ['rotate'] = {180, 0, 0},
			-- ['translate.x'] = 0,
			-- ['translate.y'] = 0,
			-- ['translate.z'] = 0,
			-- ['translate'] = {0, -char.height * .25, 0},
			['color'] = {1, 1, 1, 1}
		},
		['animations'] = {
			['scale.x'] = {
			},
			['scale.y'] = {
			},
			['scale.z'] = {
			},
			['scale'] = {
				{0, 1, {0, 0, 0}, {1, 1, 1}, {0,.8,.65,.9}}
			},
			['rotate.x'] = {
			},
			['rotate.y'] = {
			},
			['rotate.z'] = {
				-- {0, 1, 0, 360, Amaz.Ease.linear},
			},
			['rotate'] = {
				-- {.3, .6, {180, 0, 0}, {0, 0, 0}, Amaz.Ease.linear},
			},
			['translate.x'] = {
			},
			['translate.y'] = {
				-- {0, .6, -char.height * .25, char.height, {.85,.09,1,1.01}},
				-- {.6, 1, char.height, 0, Amaz.Ease.BounceOut},
			},
			['translate.z'] = {
			},
			['translate'] = {
				-- {0, 1, {0, -char.height, 0}, {0, 0, 0}, Amaz.Ease.linear},
			},
			['color.x'] = {
			},
			['color.y'] = {
			},
			['color.z'] = {
			},
			['color.w'] = {
			},
			['color'] = {
				-- {0, 1, {1, 1, 1, 0}, {1, 1, 1, 1}, Amaz.Ease.linear},
			},
		}
	}
end

function Transform:seek(time)
	time = time
	self.count = self.text.chars:size()
	--qiuchuhuanxingfudegeshu
	local enterSum = 0
	for i = 1, self.count do
		local char = self.text.chars:get(i - 1)
		if char.rowth == -1 then
			enterSum = enterSum + 1
		end
	end

	local curEnter = 0
	for i = 1, self.count do
		local char = self.text.chars:get(i - 1)

		local translate = Amaz.Vector3f(0, 0, 0)
		local rotate = Amaz.Vector3f(0, 0, 0)
		local scale = Amaz.Vector3f(0, 0, 0)
		local color = Amaz.Vector4f(0, 0, 0, 0)

		local setValue = function (name, value)
			if name == 'translate.x' then
				translate.x = value
			elseif name == 'translate.y' then
				translate.y = value
			elseif name == 'translate.z' then
				translate.z = value
			elseif name == 'translate' and type(value) == 'table' then
				translate:set(value[1], value[2], value[3])
			elseif name == 'rotate.x' then
				rotate.x = value
			elseif name == 'rotate.y' then
				rotate.y = value
			elseif name == 'rotate.z' then
				rotate.z = value
			elseif name == 'rotate' and type(value) == 'table' then
				rotate:set(value[1], value[2], value[3])
			elseif name == 'scale.x' then
				scale.x = value
			elseif name == 'scale.y' then
				scale.y = value
			elseif name == 'scale.z' then
				scale.z = value
			elseif name == 'scale' and type(value) == 'table' then
				scale:set(value[1], value[2], value[3])
			elseif name == 'color.x' then
				color.x = value
			elseif name == 'color.y' then
				color.y = value
			elseif name == 'color.z' then
				color.z = value
			elseif name == 'color.w' then
				color.w = value
			elseif name == 'color' and type(value) == 'table' then
				color:set(value[1], value[2], value[3], value[4])
			end
		end

		local info = animate(char, self.count)

		local nt = 0

		if info.mode == 0 then
			-- if self.count > 1 then
			-- 	-- jiarumeigewenzidonghuazhan0.8，ze1-.8weisuoyouzideyanchizonghe，cankaohuadongchuangkoudesheji
			-- 	-- lateweimeigeziqishiquanjuguiyihuashijian
			-- end
			if char.rowth == -1 then
				curEnter = curEnter + 1
			end
			local late = 0
			if enterSum > 0 then
				late = (1 - info.duration) / (enterSum) * curEnter * delayFactor
			end
			if time / self.duration >= late then
				-- xianqiudemeigezisuojingguodequanjuguiyihuashijian，chuyidonghuazhanbi，zeweidangezideguiyihuashijian
				nt = saturate((time / self.duration - late) / info.duration)
			end
		else
			local duration = Amaz.Ease.linear((self.count - i + 1) / self.count, 0, self.duration, 1)
			nt = (time - (self.duration - duration)) / duration
		end

		for key, value in pairs(info.default) do
			setValue(key, value)
		end

		--shezhixuliezhengdonghua
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
						if type(keyframe[3]) == 'number' and type(keyframe[4]) == 'number' then
							setValue(key, func(nt - keyframe[1], keyframe[3], keyframe[4] - keyframe[3], keyframe[2] - keyframe[1]))
						elseif type(keyframe[3]) == 'table'
							and type(keyframe[4]) == 'table'
							and #keyframe[3] == #keyframe[4] then
							local values = {}
							for i = 1, #keyframe[3] do
								--{0, 1, {1, 1, 1}, {0, 0, 0}, {.75,.02,.95,.56}},nt - 0daibiaodangqianshijian,b = 1,c = -1,biaoshicong[1,0]shisuofang,2-1=1biaoshidurationshi1
								values[i] = func(nt - keyframe[1], keyframe[3][i], keyframe[4][i] - keyframe[3][i], keyframe[2] - keyframe[1])
							end
							setValue(key, values)
						end
					end
					break
				elseif nt < keyframe[1] then
					if index > 1 then
						setValue(key, value[index - 1][4])
					end
					break
				elseif nt > keyframe[2] then
					setValue(key, value[index][4])
				end
			end
		end

		local halfWidth = char.width / 3
		local halfHeight = char.height / 3
		-- 0 1 => 1 -1
		local anchor = Amaz.Vector4f(
			remap(-.5, .5, -(1 - scale.x), 1 - scale.x, info['anchor'][1]) * halfWidth + remap(-.5, .5, 1, -1, info['pivot'][1]) * halfWidth,
			remap(-.5, .5, -(1 - scale.y), 1 - scale.y, info['anchor'][2]) * halfHeight + remap(-.5, .5, 1, -1, info['pivot'][2]) * halfHeight,
			0,
			1
		)
		local mat = Amaz.Matrix4x4f()
		mat:setTRS(
			Amaz.Vector3f(
				remap(-.5, .5, -1, 1, info['pivot'][1]) * halfWidth,
				remap(-.5, .5, -1, 1, info['pivot'][2]) * halfHeight,
				-- lerp(-char.width / 3, char.width / 3, remap(-.5, .5, 0, 1, info['anchor'][1])),
				-- lerp(-char.height / 3, char.height / 3, remap(-.5, .5, 0, 1, info['anchor'][2])),
				0
			),
			Amaz.Quaternionf.eulerToQuaternion(Amaz.Vector3f(rotate.x / 180 * math.pi, rotate.y / 180 * math.pi, rotate.z / 180 * math.pi)),
			Amaz.Vector3f(1, 1, 1)
		)
		anchor = mat:multiplyVector4(anchor)
		-- point.x = math.cos(rotate.z / 180 * math.pi) * anchor.x - math.sin(rotate.z / 180 * math.pi) * anchor.y
		-- point.y = math.sin(rotate.z / 180 * math.pi) * anchor.x + math.cos(rotate.z / 180 * math.pi) * anchor.y
		-- -- anchor offset
		-- point.x = point.x + lerp(-char.width / 3, char.width / 3, remap(-.5, .5, 0, 1, info['anchor.x']))
		-- point.y = point.y + lerp(-char.height / 3, char.height / 3, remap(-.5, .5, 0, 1, info['anchor.y']))
		char.rotate = rotate
		char.scale = scale
		char.position = char.initialPosition + Amaz.Vector3f(anchor.x, anchor.y, anchor.z) + translate
		char.color = color
	end

    local chars = self.text.chars 
    self.text.chars= chars
end

function Transform:setDuration(duration)
   self.duration = duration
end

function Transform:clear()
	for i = 1, self.text.chars:size() do
        local char = self.text.chars:get(i - 1)
        if char.rowth ~= -1 then
            char.position = char.initialPosition
            char.rotate = Amaz.Vector3f(0, 0, 0)
            char.scale = Amaz.Vector3f(1, 1, 1)
            char.color = Amaz.Vector4f(1, 1, 1, 1)
        end
    end
    if self.text ~= nil then
    	local chars = self.text.chars 
   		self.text.chars= chars
   	end
end

exports.Transform = Transform
return exports
